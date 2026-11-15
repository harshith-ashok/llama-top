"""Background workers: source polling, local host sampling and retention."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from sqlalchemy import delete, select

from . import adapters
from .collector import Collector
from .config import get_settings
from .db import Host, HostMetric, Model, RequestLog, Source, session

log = logging.getLogger("llamatop")

LOCAL_HOST_ID = "local"
# Latest full sample per host (includes the process list, which is not persisted).
latest: dict[str, dict[str, Any]] = {}


def store_sample(
    host_id: str, name: str, kind: str, info: dict[str, Any] | None, sample: dict[str, Any]
) -> None:
    latest[host_id] = sample
    persisted = {k: v for k, v in sample.items() if k != "processes"}
    with session() as s:
        host = s.get(Host, host_id)
        if host is None:
            host = Host(id=host_id, name=name, kind=kind, info=info or {})
            s.add(host)
        host.name = name
        host.last_seen = sample["ts"]
        if info:
            host.info = info
        s.add(HostMetric(host_id=host_id, ts=sample["ts"], data=persisted))
        s.commit()


def _apply_probe(source_id: str, res: adapters.ProbeResult) -> None:
    with session() as s:
        src = s.get(Source, source_id)
        if src is None:
            return
        src.status = res.status
        src.latency_ms = res.latency_ms
        src.error = res.error
        src.capabilities = res.capabilities
        if res.status != "offline":
            src.last_seen = time.time()
            src.version = res.version
            s.execute(delete(Model).where(Model.source_id == source_id))
            for m in res.models:
                s.add(
                    Model(
                        source_id=source_id,
                        **{k: v for k, v in m.items() if k in Model.__table__.columns.keys()},
                    )
                )
        s.commit()


def agent_host_id(source_id: str) -> str:
    return f"src-{source_id}"


def forget_host(db, source_id: str) -> None:
    hid = agent_host_id(source_id)
    db.execute(delete(HostMetric).where(HostMetric.host_id == hid))
    db.execute(delete(Host).where(Host.id == hid))
    latest.pop(hid, None)


async def pull_agent(client: httpx.AsyncClient, source_id: str) -> None:
    """Pull host metrics from the agent attached to a source (pull mode)."""
    with session() as s:
        src = s.get(Source, source_id)
        if src is None or not src.agent_url:
            return
        url, token, name = src.agent_url, src.agent_token, src.name
    error: str | None = None
    try:
        r = await client.get(
            f"{url}/metrics",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=adapters.TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        sample = data["sample"]
        sample["ts"] = time.time()  # trust the dashboard clock
        await asyncio.to_thread(
            store_sample, agent_host_id(source_id), name, "agent", data.get("info"), sample
        )
    except Exception as e:  # noqa: BLE001
        error = adapters._err(e)
    with session() as s:
        src = s.get(Source, source_id)
        if src is not None:
            src.agent_error = error
            s.commit()


async def probe_source(client: httpx.AsyncClient, source_id: str) -> None:
    with session() as s:
        src = s.get(Source, source_id)
        if src is None:
            return
        args = (src.type, src.base_url, src.api_key)
    res = await adapters.probe(client, *args)
    await asyncio.to_thread(_apply_probe, source_id, res)
    await pull_agent(client, source_id)


async def poll_loop(client: httpx.AsyncClient) -> None:
    interval = get_settings().poll_interval
    while True:
        try:
            with session() as s:
                ids = list(s.scalars(select(Source.id).where(Source.enabled.is_(True))))
            await asyncio.gather(*(probe_source(client, i) for i in ids), return_exceptions=True)
        except Exception:  # noqa: BLE001
            log.exception("poll failed")
        await asyncio.sleep(interval)


async def host_loop() -> None:
    cfg = get_settings()
    collector = await asyncio.to_thread(Collector)
    info = await asyncio.to_thread(collector.info)
    name = cfg.local_host_name or info["hostname"]
    while True:
        try:
            sample = await asyncio.to_thread(collector.sample)
            await asyncio.to_thread(store_sample, LOCAL_HOST_ID, name, "local", info, sample)
        except Exception:  # noqa: BLE001
            log.exception("host sampling failed")
        await asyncio.sleep(cfg.metrics_interval)


def prune() -> None:
    cutoff = time.time() - get_settings().retention_days * 86400
    with session() as s:
        s.execute(delete(HostMetric).where(HostMetric.ts < cutoff))
        s.execute(delete(RequestLog).where(RequestLog.ts < cutoff))
        s.commit()


async def retention_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(prune)
        except Exception:  # noqa: BLE001
            log.exception("prune failed")
        await asyncio.sleep(3600)


def seed_default_source() -> None:
    url = get_settings().default_ollama_url
    if not url:
        return
    with session() as s:
        if s.scalars(select(Source).limit(1)).first() is None:
            s.add(Source(name="Local Ollama", type="ollama", base_url=url, tags=["local"]))
            s.commit()

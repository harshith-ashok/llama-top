"""Provider adapters. Each reports health, models and the capabilities it supports."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

TIMEOUT = httpx.Timeout(8.0, connect=4.0)


@dataclass
class ProbeResult:
    status: str = "offline"  # online | degraded | offline
    latency_ms: float | None = None
    version: str | None = None
    error: str | None = None
    capabilities: list[str] = field(default_factory=list)
    models: list[dict[str, Any]] = field(default_factory=list)


def auth_headers(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _details(m: dict[str, Any]) -> dict[str, Any]:
    d = m.get("details") or {}
    return {
        "family": d.get("family"),
        "parameter_size": d.get("parameter_size"),
        "quantization": d.get("quantization_level"),
        "format": d.get("format"),
    }


async def probe_ollama(client: httpx.AsyncClient, base: str, api_key: str | None) -> ProbeResult:
    base = base.rstrip("/")
    h = auth_headers(api_key)
    res = ProbeResult()
    t0 = time.monotonic()
    try:
        r = await client.get(f"{base}/api/version", headers=h, timeout=TIMEOUT)
        res.latency_ms = (time.monotonic() - t0) * 1000
        r.raise_for_status()
        res.version = r.json().get("version")
    except Exception as e:  # noqa: BLE001 - surfaced to the UI as the error string
        res.error = _err(e)
        return res
    res.status = "online"
    res.capabilities = ["health", "version"]
    loaded: dict[str, dict[str, Any]] = {}
    try:
        r = await client.get(f"{base}/api/ps", headers=h, timeout=TIMEOUT)
        r.raise_for_status()
        loaded = {m.get("name") or m.get("model"): m for m in r.json().get("models", [])}
        res.capabilities.append("loaded_models")
    except Exception:  # noqa: BLE001
        pass
    try:
        r = await client.get(f"{base}/api/tags", headers=h, timeout=TIMEOUT)
        r.raise_for_status()
        res.capabilities.append("model_inventory")
        for m in r.json().get("models", []):
            name = m.get("name") or m.get("model")
            ps = loaded.get(name, {})
            res.models.append(
                {
                    "name": name,
                    "digest": m.get("digest"),
                    "size_bytes": m.get("size"),
                    "modified_at": m.get("modified_at"),
                    "loaded": name in loaded,
                    "vram_bytes": ps.get("size_vram"),
                    "expires_at": ps.get("expires_at"),
                    "raw": m,
                    **_details(m),
                }
            )
    except Exception as e:  # noqa: BLE001
        res.status = "degraded"
        res.error = _err(e)
    return res


async def probe_openai(client: httpx.AsyncClient, base: str, api_key: str | None) -> ProbeResult:
    base = base.rstrip("/")
    res = ProbeResult()
    t0 = time.monotonic()
    try:
        r = await client.get(f"{base}/models", headers=auth_headers(api_key), timeout=TIMEOUT)
        res.latency_ms = (time.monotonic() - t0) * 1000
        r.raise_for_status()
        data = r.json().get("data", [])
    except Exception as e:  # noqa: BLE001
        res.error = _err(e)
        return res
    res.status = "online"
    res.capabilities = ["health", "model_listing"]
    res.version = r.headers.get("server")
    for m in data:
        res.models.append({"name": m.get("id"), "raw": m, "loaded": False})
    return res


def _err(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    return f"{type(e).__name__}: {e}"[:200] or type(e).__name__


async def probe(client: httpx.AsyncClient, source_type: str, base: str, key: str | None):
    if source_type == "ollama":
        return await probe_ollama(client, base, key)
    return await probe_openai(client, base, key)

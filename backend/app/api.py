from __future__ import annotations

import hmac
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import Integer, String, case, cast, func, select
from sqlalchemy.orm import Session

from . import runtime
from .config import get_settings
from .db import Host, HostMetric, Model, RequestLog, Source, get_db

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- sources ---
class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["ollama", "openai"]
    base_url: HttpUrl
    api_key: str | None = None
    tags: list[str] = []
    enabled: bool = True
    agent_url: HttpUrl | None = None
    agent_token: str | None = None


class SourcePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: HttpUrl | None = None
    api_key: str | None = None
    clear_api_key: bool = False
    tags: list[str] | None = None
    enabled: bool | None = None
    agent_url: HttpUrl | None = None
    agent_token: str | None = None
    clear_agent: bool = False


def source_out(s: Source, db: Session) -> dict[str, Any]:
    n = db.scalar(select(func.count()).select_from(Model).where(Model.source_id == s.id))
    return {
        "id": s.id,
        "name": s.name,
        "type": s.type,
        "base_url": s.base_url,
        "has_api_key": bool(s.api_key),
        "tags": s.tags,
        "enabled": s.enabled,
        "status": s.status if s.enabled else "disabled",
        "last_seen": s.last_seen,
        "latency_ms": s.latency_ms,
        "version": s.version,
        "error": s.error,
        "capabilities": s.capabilities,
        "model_count": n or 0,
        "gateway_path": f"/gateway/{s.id}",
        "agent_url": s.agent_url,
        "agent_error": s.agent_error,
        "host_id": runtime.agent_host_id(s.id) if s.agent_url else None,
    }


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    return [source_out(s, db) for s in db.scalars(select(Source).order_by(Source.created_at))]


@router.post("/sources", status_code=201)
async def add_source(body: SourceIn, request: Request, db: Session = Depends(get_db)):
    src = Source(
        name=body.name,
        type=body.type,
        base_url=str(body.base_url).rstrip("/"),
        api_key=body.api_key or None,
        tags=body.tags,
        enabled=body.enabled,
        agent_url=str(body.agent_url).rstrip("/") if body.agent_url else None,
        agent_token=body.agent_token or None,
    )
    db.add(src)
    db.commit()
    if src.enabled:
        await runtime.probe_source(request.app.state.http, src.id)
        db.refresh(src)
    return source_out(src, db)


def _get_source(db: Session, source_id: str) -> Source:
    src = db.get(Source, source_id)
    if src is None:
        raise HTTPException(404, "source not found")
    return src


@router.patch("/sources/{source_id}")
async def edit_source(
    source_id: str, body: SourcePatch, request: Request, db: Session = Depends(get_db)
):
    src = _get_source(db, source_id)
    if body.name is not None:
        src.name = body.name
    if body.base_url is not None:
        src.base_url = str(body.base_url).rstrip("/")
    if body.clear_api_key:
        src.api_key = None
    elif body.api_key:
        src.api_key = body.api_key
    if body.tags is not None:
        src.tags = body.tags
    if body.enabled is not None:
        src.enabled = body.enabled
    if body.clear_agent:
        src.agent_url = src.agent_token = src.agent_error = None
        runtime.forget_host(db, source_id)
    else:
        if body.agent_url is not None:
            src.agent_url = str(body.agent_url).rstrip("/")
        if body.agent_token:
            src.agent_token = body.agent_token
    db.commit()
    if src.enabled:
        await runtime.probe_source(request.app.state.http, src.id)
        db.refresh(src)
    return source_out(src, db)


@router.delete("/sources/{source_id}", status_code=204)
def remove_source(source_id: str, db: Session = Depends(get_db)):
    src = _get_source(db, source_id)
    db.query(Model).filter(Model.source_id == source_id).delete()
    runtime.forget_host(db, source_id)
    db.delete(src)
    db.commit()


@router.post("/sources/{source_id}/check")
async def check_source(source_id: str, request: Request, db: Session = Depends(get_db)):
    src = _get_source(db, source_id)
    await runtime.probe_source(request.app.state.http, src.id)
    db.refresh(src)
    return source_out(src, db)


# ----------------------------------------------------------------- models ---
@router.get("/models")
def list_models(q: str | None = None, source_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Model, Source.name).join(Source, Source.id == Model.source_id)
    if q:
        stmt = stmt.where(Model.name.ilike(f"%{q}%"))
    if source_id:
        stmt = stmt.where(Model.source_id == source_id)
    rows = db.execute(stmt.order_by(Model.name)).all()
    return [
        {
            "source_id": m.source_id,
            "source_name": sname,
            "name": m.name,
            "digest": m.digest,
            "size_bytes": m.size_bytes,
            "family": m.family,
            "parameter_size": m.parameter_size,
            "quantization": m.quantization,
            "format": m.format,
            "loaded": m.loaded,
            "vram_bytes": m.vram_bytes,
            "expires_at": m.expires_at,
            "modified_at": m.modified_at,
        }
        for m, sname in rows
    ]


# ------------------------------------------------------------------- host ---
class IngestIn(BaseModel):
    host_id: str = Field(min_length=1, max_length=64, pattern=r"^[\w.-]+$")
    name: str
    info: dict[str, Any] | None = None
    sample: dict[str, Any]


@router.post("/agent/ingest", status_code=204)
def ingest(body: IngestIn, authorization: str = Header(default="")):
    token = get_settings().agent_token
    supplied = authorization.removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(supplied, token):
        raise HTTPException(401, "invalid or unconfigured agent token")
    if body.host_id == runtime.LOCAL_HOST_ID:
        raise HTTPException(400, "reserved host id")
    body.sample["ts"] = time.time()  # trust the server clock
    runtime.store_sample(body.host_id, body.name, "agent", body.info, body.sample)


@router.get("/hosts")
def list_hosts(db: Session = Depends(get_db)):
    now = time.time()
    out = []
    for h in db.scalars(select(Host).order_by(Host.kind, Host.name)):
        age = now - h.last_seen if h.last_seen else None
        out.append(
            {
                "id": h.id,
                "name": h.name,
                "kind": h.kind,
                "last_seen": h.last_seen,
                "online": age is not None and age < 30,
                "info": h.info,
                "current": runtime.latest.get(h.id),
            }
        )
    return out


@router.get("/hosts/{host_id}/history")
def host_history(
    host_id: str, minutes: int = Query(60, ge=1, le=7 * 1440), db: Session = Depends(get_db)
):
    since = time.time() - minutes * 60
    rows = db.execute(
        select(HostMetric.ts, HostMetric.data)
        .where(HostMetric.host_id == host_id, HostMetric.ts >= since)
        .order_by(HostMetric.ts)
    ).all()
    step = max(1, len(rows) // 600)  # cap payload at ~600 points
    return [
        {"ts": ts, **{k: d.get(k) for k in ("cpu", "memory", "gpus", "network", "disk_io")}}
        for ts, d in rows[::step]
    ]


# --------------------------------------------------------------- requests ---
def _req_out(r: RequestLog) -> dict[str, Any]:
    cols = RequestLog.__table__.columns.keys()
    return {c: getattr(r, c) for c in cols}


@router.get("/requests")
def list_requests(
    limit: int = Query(100, ge=1, le=500),
    source_id: str | None = None,
    model: str | None = None,
    errors_only: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(RequestLog).order_by(RequestLog.ts.desc()).limit(limit)
    if source_id:
        stmt = stmt.where(RequestLog.source_id == source_id)
    if model:
        stmt = stmt.where(RequestLog.model == model)
    if errors_only:
        stmt = stmt.where(RequestLog.status >= 400)
    return [_req_out(r) for r in db.scalars(stmt)]


# -------------------------------------------------------------- analytics ---
def _since(hours: int) -> float:
    return time.time() - hours * 3600


@router.get("/analytics/summary")
def analytics_summary(hours: int = Query(24, ge=1, le=24 * 30), db: Session = Depends(get_db)):
    r = RequestLog
    row = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(r.prompt_tokens), 0),
            func.coalesce(func.sum(r.completion_tokens), 0),
            func.avg(r.gen_tps),
            func.avg(r.prompt_tps),
            func.avg(r.ttft_ms),
            func.avg(r.latency_ms),
            func.coalesce(func.sum(case((r.status >= 400, 1), else_=0)), 0),
        ).where(r.ts >= _since(hours))
    ).one()
    total, pt, ct, gtps, ptps, ttft, lat, errs = row
    return {
        "hours": hours,
        "requests": total,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": pt + ct,
        "avg_gen_tps": gtps,
        "avg_prompt_tps": ptps,
        "avg_ttft_ms": ttft,
        "avg_latency_ms": lat,
        "errors": errs,
        "error_rate": (errs / total) if total else 0.0,
    }


@router.get("/analytics/timeseries")
def analytics_timeseries(hours: int = Query(24, ge=1, le=24 * 30), db: Session = Depends(get_db)):
    r = RequestLog
    bucket = max(60, hours * 3600 // 120)  # ~120 points
    b = cast(r.ts / bucket, Integer) * bucket
    rows = db.execute(
        select(
            b.label("t"),
            func.count(),
            func.coalesce(func.sum(r.prompt_tokens), 0),
            func.coalesce(func.sum(r.completion_tokens), 0),
            func.avg(r.gen_tps),
            func.avg(r.latency_ms),
        )
        .where(r.ts >= _since(hours))
        .group_by("t")
        .order_by("t")
    ).all()
    return [
        {
            "ts": t,
            "requests": n,
            "prompt_tokens": p,
            "completion_tokens": c,
            "avg_gen_tps": g,
            "avg_latency_ms": lat,
        }
        for t, n, p, c, g, lat in rows
    ]


@router.get("/analytics/models")
def analytics_models(hours: int = Query(24, ge=1, le=24 * 30), db: Session = Depends(get_db)):
    r = RequestLog
    rows = db.execute(
        select(
            func.coalesce(r.model, cast("unknown", String)),
            r.source_id,
            func.count(),
            func.coalesce(func.sum(r.prompt_tokens), 0),
            func.coalesce(func.sum(r.completion_tokens), 0),
            func.avg(r.gen_tps),
            func.avg(r.prompt_tps),
            func.avg(r.ttft_ms),
            func.avg(r.latency_ms),
            func.coalesce(func.sum(case((r.status >= 400, 1), else_=0)), 0),
        )
        .where(r.ts >= _since(hours))
        .group_by(r.model, r.source_id)
        .order_by(func.count().desc())
    ).all()
    keys = (
        "model",
        "source_id",
        "requests",
        "prompt_tokens",
        "completion_tokens",
        "avg_gen_tps",
        "avg_prompt_tps",
        "avg_ttft_ms",
        "avg_latency_ms",
        "errors",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


@router.get("/health")
def health():
    return {"status": "ok"}

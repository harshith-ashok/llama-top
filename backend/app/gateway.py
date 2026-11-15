"""Transparent recording proxy.

Point clients at ``/gateway/<source_id>`` instead of the provider. Requests are
forwarded unchanged (streaming included) while normalized metrics are recorded.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .db import RequestLog, Source, session
from .parsers import UsageParser, classify, request_info

router = APIRouter()

HOP = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "accept-encoding",
    "upgrade",
    "te",
    "trailer",
}
RESP_HOP = HOP | {"content-encoding"}
STREAM_TIMEOUT = httpx.Timeout(None, connect=10.0)


def _record(row: RequestLog) -> None:
    with session() as s:
        s.add(row)
        s.commit()


@router.api_route(
    "/gateway/{source_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD"]
)
async def gateway(source_id: str, path: str, request: Request) -> StreamingResponse:
    with session() as s:
        src = s.get(Source, source_id)
        if src is None:
            raise HTTPException(404, "unknown source")
        base, key = src.base_url.rstrip("/"), src.api_key
        ollama = src.type == "ollama"

    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    headers["accept-encoding"] = "identity"
    if key and "authorization" not in {k.lower() for k in headers}:
        headers["authorization"] = f"Bearer {key}"

    kind = classify(path)
    info = request_info(body) if kind else {}
    app_name = request.headers.get("x-llamatop-app")
    session_id = request.headers.get("x-llamatop-session")
    url = f"{base}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    client: httpx.AsyncClient = request.app.state.http
    started_wall, started = time.time(), time.monotonic()
    upstream_req = client.build_request(
        request.method, url, headers=headers, content=body, timeout=STREAM_TIMEOUT
    )

    def row(status: int, error: str | None, parser: UsageParser | None) -> RequestLog:
        m = parser.finish() if parser else {}
        return RequestLog(
            source_id=source_id,
            ts=started_wall,
            model=info.get("model"),
            endpoint=f"/{path}",
            method=request.method,
            status=status,
            stream=info.get("stream", False),
            latency_ms=(time.monotonic() - started) * 1000,
            params=info.get("params", {}),
            app=app_name,
            session=session_id,
            prompt_tokens=m.get("prompt_tokens"),
            completion_tokens=m.get("completion_tokens"),
            cached_tokens=m.get("cached_tokens"),
            reasoning_tokens=m.get("reasoning_tokens"),
            ttft_ms=m.get("ttft_ms"),
            gen_tps=m.get("gen_tps"),
            prompt_tps=m.get("prompt_tps"),
            load_ms=m.get("load_ms"),
            finish_reason=m.get("finish_reason"),
            error=error or m.get("error"),
            raw_usage=m.get("raw_usage", {}),
        )

    try:
        upstream = await client.send(upstream_req, stream=True)
    except httpx.HTTPError as e:
        if kind:
            await asyncio.to_thread(_record, row(502, f"{type(e).__name__}: {e}"[:200], None))
        raise HTTPException(502, f"upstream unreachable: {type(e).__name__}") from e

    parser = UsageParser(started, ollama) if kind else None
    ctype = upstream.headers.get("content-type", "")

    async def body_iter() -> AsyncIterator[bytes]:
        error: str | None = None
        try:
            async for chunk in upstream.aiter_raw():
                if parser:
                    parser.feed(chunk, ctype)
                yield chunk
        except (httpx.HTTPError, asyncio.CancelledError) as e:
            error = "client disconnected" if isinstance(e, asyncio.CancelledError) else str(e)[:200]
            raise
        finally:
            await upstream.aclose()
            if kind:
                status = upstream.status_code
                if status >= 400 and not error:
                    error = f"HTTP {status}"
                await asyncio.shield(asyncio.to_thread(_record, row(status, error, parser)))

    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in RESP_HOP}
    return StreamingResponse(body_iter(), status_code=upstream.status_code, headers=out_headers)

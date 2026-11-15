from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from . import runtime
from .api import router as api_router
from .config import get_settings
from .db import init_engine
from .gateway import router as gateway_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    init_engine()
    runtime.seed_default_source()
    app.state.http = httpx.AsyncClient(follow_redirects=False)
    tasks = [
        asyncio.create_task(runtime.poll_loop(app.state.http)),
        asyncio.create_task(runtime.retention_loop()),
    ]
    if cfg.collect_local_host:
        tasks.append(asyncio.create_task(runtime.host_loop()))
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await app.state.http.aclose()


app = FastAPI(title="llama-top", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)
app.include_router(gateway_router)

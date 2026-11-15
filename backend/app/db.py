from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

from sqlalchemy import JSON, Boolean, Float, Integer, String, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import get_settings


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # ollama | openai
    base_url: Mapped[str] = mapped_column(String)
    api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="unknown")
    last_seen: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    # Optional pull-mode host agent running on the same machine as the source.
    agent_url: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_token: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_error: Mapped[str | None] = mapped_column(String, nullable=True)


class Model(Base):
    __tablename__ = "models"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    digest: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    family: Mapped[str | None] = mapped_column(String, nullable=True)
    parameter_size: Mapped[str | None] = mapped_column(String, nullable=True)
    quantization: Mapped[str | None] = mapped_column(String, nullable=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)
    loaded: Mapped[bool] = mapped_column(Boolean, default=False)
    vram_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    modified_at: Mapped[str | None] = mapped_column(String, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Host(Base):
    __tablename__ = "hosts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="agent")  # local | agent
    last_seen: Mapped[float | None] = mapped_column(Float, nullable=True)
    info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class HostMetric(Base):
    __tablename__ = "host_metrics"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    host_id: Mapped[str] = mapped_column(String, index=True)
    ts: Mapped[float] = mapped_column(Float, index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class RequestLog(Base):
    __tablename__ = "requests"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    source_id: Mapped[str] = mapped_column(String, index=True)
    ts: Mapped[float] = mapped_column(Float, index=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    status: Mapped[int] = mapped_column(Integer)
    stream: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    gen_tps: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tps: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    app: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    session: Mapped[str | None] = mapped_column(String, nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Provider usage as reported, retained alongside the normalized columns.
    raw_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


_engine = None
_Session: sessionmaker[Session] | None = None


def init_engine(url: str | None = None) -> None:
    global _engine, _Session
    url = url or get_settings().database_url
    kwargs: dict[str, Any] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        path = url.split("///", 1)[-1]
        if path and path != ":memory:" and os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
    _engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _pragmas(conn, _):  # type: ignore[no-untyped-def]
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

    Base.metadata.create_all(_engine)
    _add_missing_columns()
    _Session = sessionmaker(_engine, expire_on_commit=False)


def session() -> Session:
    assert _Session is not None, "init_engine() not called"
    return _Session()


def get_db() -> Iterator[Session]:
    with session() as s:
        yield s


def _add_missing_columns() -> None:
    """Tiny forward-only migration: add columns introduced after a table was created."""
    assert _engine is not None
    insp = inspect(_engine)
    with _engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    ddl = col.type.compile(dialect=_engine.dialect)
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}"))

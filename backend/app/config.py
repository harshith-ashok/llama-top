from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./data/llamatop.db")
    )
    poll_interval: int = field(default_factory=lambda: _int("POLL_INTERVAL", 10))
    metrics_interval: int = field(default_factory=lambda: _int("METRICS_INTERVAL", 5))
    retention_days: int = field(default_factory=lambda: _int("RETENTION_DAYS", 7))
    # Shared secret agents must present. Ingest is disabled when empty.
    agent_token: str = field(default_factory=lambda: os.environ.get("AGENT_TOKEN", ""))
    # Optional source seeded on first start, e.g. http://host.docker.internal:11434
    default_ollama_url: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_OLLAMA_URL", "")
    )
    local_host_name: str = field(default_factory=lambda: os.environ.get("LOCAL_HOST_NAME", ""))
    collect_local_host: bool = field(
        default_factory=lambda: os.environ.get("COLLECT_LOCAL_HOST", "true").lower() != "false"
    )


def get_settings() -> Settings:
    return Settings()

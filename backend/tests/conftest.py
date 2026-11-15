import os
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp).as_posix()}/test.db"
os.environ["COLLECT_LOCAL_HOST"] = "false"
os.environ["POLL_INTERVAL"] = "3600"
os.environ["AGENT_TOKEN"] = "secret"

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def use_upstream(handler):
    """Route all outbound provider traffic through ``handler`` instead of the network."""
    app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

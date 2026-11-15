import json

import httpx

from .conftest import use_upstream


class Chunks(httpx.AsyncByteStream):
    def __init__(self, parts):
        self.parts = parts

    async def __aiter__(self):
        for p in self.parts:
            yield p


def ollama_upstream(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/version":
        return httpx.Response(200, json={"version": "0.9.0"})
    if path == "/api/tags":
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "llama3:8b",
                        "digest": "abc",
                        "size": 4_700_000_000,
                        "details": {
                            "family": "llama",
                            "parameter_size": "8B",
                            "quantization_level": "Q4_0",
                        },
                    }
                ]
            },
        )
    if path == "/api/ps":
        return httpx.Response(200, json={"models": [{"name": "llama3:8b", "size_vram": 5}]})
    if path == "/api/chat":
        lines = [
            {"message": {"content": "hey"}, "done": False},
            {
                "done": True,
                "done_reason": "stop",
                "eval_count": 20,
                "eval_duration": 1_000_000_000,
                "prompt_eval_count": 5,
                "prompt_eval_duration": 100_000_000,
            },
        ]
        return httpx.Response(
            200,
            stream=Chunks([(json.dumps(x) + "\n").encode() for x in lines]),
            headers={"content-type": "application/x-ndjson"},
        )
    return httpx.Response(404)


def add_ollama(client):
    use_upstream(ollama_upstream)
    r = client.post(
        "/api/sources",
        json={
            "name": "t",
            "type": "ollama",
            "base_url": "http://ollama.test:11434",
            "api_key": "k",
        },
    )
    assert r.status_code == 201
    return r.json()


def test_source_lifecycle_and_models(client):
    src = add_ollama(client)
    assert src["status"] == "online" and src["version"] == "0.9.0"
    assert src["has_api_key"] is True and "api_key" not in src
    assert "model_inventory" in src["capabilities"]
    models = client.get("/api/models").json()
    assert models[0]["name"] == "llama3:8b" and models[0]["loaded"] is True
    assert models[0]["quantization"] == "Q4_0"
    assert client.get("/api/models", params={"q": "nope"}).json() == []
    r = client.patch(f"/api/sources/{src['id']}", json={"enabled": False})
    assert r.json()["status"] == "disabled"
    assert client.delete(f"/api/sources/{src['id']}").status_code == 204
    assert client.get("/api/models").json() == []


def test_offline_source(client):
    use_upstream(lambda req: httpx.Response(500))
    r = client.post(
        "/api/sources", json={"name": "bad", "type": "openai", "base_url": "http://x.test/v1"}
    )
    assert r.json()["status"] == "offline"


def test_gateway_records_metrics(client):
    src = add_ollama(client)
    r = client.post(
        f"/gateway/{src['id']}/api/chat",
        json={"model": "llama3:8b", "stream": True, "messages": []},
        headers={"x-llamatop-app": "cli"},
    )
    assert r.status_code == 200 and "hey" in r.text  # body passes through untouched
    reqs = client.get("/api/requests").json()
    assert len(reqs) == 1
    q = reqs[0]
    assert q["model"] == "llama3:8b" and q["app"] == "cli" and q["status"] == 200
    assert q["completion_tokens"] == 20 and q["gen_tps"] == 20.0
    summary = client.get("/api/analytics/summary").json()
    assert summary["requests"] == 1 and summary["total_tokens"] == 25
    assert client.get("/api/analytics/models").json()[0]["model"] == "llama3:8b"
    assert len(client.get("/api/analytics/timeseries").json()) == 1


def test_gateway_unknown_source(client):
    assert client.post("/gateway/nope/api/chat", json={}).status_code == 404


def test_agent_ingest_auth(client):
    body = {"host_id": "box", "name": "box", "sample": {"cpu": {"percent": 5}}}
    assert client.post("/api/agent/ingest", json=body).status_code == 401
    h = {"Authorization": "Bearer secret"}
    assert client.post("/api/agent/ingest", json=body, headers=h).status_code == 204
    bad = {**body, "host_id": "local"}
    assert client.post("/api/agent/ingest", json=bad, headers=h).status_code == 400
    hosts = client.get("/api/hosts").json()
    assert any(x["id"] == "box" and x["online"] for x in hosts)
    assert len(client.get("/api/hosts/box/history").json()) >= 1


def test_collector_sample():
    from app.collector import Collector

    c = Collector()
    s = c.sample()
    assert 0 <= s["cpu"]["percent"] <= 100 and s["memory"]["total"] > 0
    assert "hostname" in c.info()


def test_pull_mode_agent(client):
    def upstream(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/metrics":
            if request.headers.get("authorization") != "Bearer tok":
                return httpx.Response(401)
            return httpx.Response(
                200,
                json={
                    "info": {
                        "hostname": "win-box",
                        "os": "Windows 11",
                        "gpus": [{"index": 0, "name": "RTX"}],
                    },
                    "sample": {
                        "ts": 1,
                        "cpu": {"percent": 42},
                        "memory": {"percent": 50},
                        "gpus": [],
                    },
                },
            )
        return ollama_upstream(request)

    use_upstream(upstream)
    body = {
        "name": "win",
        "type": "ollama",
        "base_url": "http://100.1.1.1:11434",
        "agent_url": "http://100.1.1.1:9100",
        "agent_token": "tok",
    }
    src = client.post("/api/sources", json=body).json()
    assert src["host_id"] == f"src-{src['id']}" and src["agent_error"] is None
    assert "agent_token" not in src
    hosts = {h["id"]: h for h in client.get("/api/hosts").json()}
    h = hosts[src["host_id"]]
    assert h["name"] == "win" and h["online"] and h["info"]["os"] == "Windows 11"
    assert h["current"]["cpu"]["percent"] == 42

    # wrong token -> surfaced as an agent error, source itself stays online
    r = client.patch(f"/api/sources/{src['id']}", json={"agent_token": "bad"}).json()
    assert r["status"] == "online" and r["agent_error"] == "HTTP 401"

    # detaching the agent removes its host
    client.patch(f"/api/sources/{src['id']}", json={"clear_agent": True})
    assert src["host_id"] not in {h["id"] for h in client.get("/api/hosts").json()}


def test_agent_serve_handler():
    import json as _json
    import threading
    from http.server import ThreadingHTTPServer

    from app.agent import make_handler
    from app.collector import Collector

    c = Collector()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(c, c.info(), "s3"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert httpx.get(f"{base}/metrics").status_code == 401
        r = httpx.get(f"{base}/metrics", headers={"Authorization": "Bearer s3"})
        data = _json.loads(r.text)
        assert data["sample"]["memory"]["total"] > 0 and "hostname" in data["info"]
    finally:
        srv.shutdown()

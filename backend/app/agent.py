"""Host agent: samples this machine's CPU/RAM/GPU/disk/network for a llama-top dashboard.

Pull mode (recommended for remote machines; the dashboard fetches from the agent):
    llamatop-agent --serve --token SECRET --host 100.74.98.40 --port 9100

Push mode (the agent posts to the dashboard; needs the dashboard reachable and AGENT_TOKEN set):
    llamatop-agent --server http://dashboard:3000 --token SECRET --name gpu-box
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .collector import Collector


def make_handler(collector: Collector, info: dict, token: str):
    lock = threading.Lock()  # the collector keeps delta state between samples

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(supplied, token):
                return self._send(401, {"detail": "invalid token"})
            if self.path.split("?")[0] == "/metrics":
                with lock:
                    sample = collector.sample()
                return self._send(200, {"info": info, "sample": sample})
            self._send(404, {"detail": "not found"})

        def log_message(self, *_args) -> None:  # keep the console quiet
            pass

    return Handler


def serve(host: str, port: int, token: str) -> None:
    collector = Collector()
    handler = make_handler(collector, collector.info(), token)
    print(f"llama-top agent serving on http://{host}:{port}/metrics", flush=True)
    ThreadingHTTPServer((host, port), handler).serve_forever()


def push(server: str, token: str, name: str, interval: float) -> None:
    import httpx

    host_id = re.sub(r"[^\w.-]", "-", name)
    collector = Collector()
    info = collector.info()
    url = server.rstrip("/") + "/api/agent/ingest"
    with httpx.Client(timeout=10, headers={"Authorization": f"Bearer {token}"}) as client:
        while True:
            try:
                r = client.post(
                    url,
                    json={
                        "host_id": host_id,
                        "name": name,
                        "info": info,
                        "sample": collector.sample(),
                    },
                )
                r.raise_for_status()
            except httpx.HTTPError as e:
                print(f"push failed: {e}", flush=True)
            time.sleep(interval)


def main() -> None:
    env = os.environ.get
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--token", default=env("AGENT_TOKEN", ""), help="shared secret (required)")
    ap.add_argument("--serve", action="store_true", help="pull mode: expose /metrics")
    ap.add_argument("--host", default=env("AGENT_HOST", "0.0.0.0"), help="serve: bind address")
    ap.add_argument("--port", type=int, default=int(env("AGENT_PORT", 9100)), help="serve: port")
    ap.add_argument("--server", default=env("LLAMATOP_SERVER", "http://localhost:3000"))
    ap.add_argument("--name", default=env("AGENT_NAME", socket.gethostname()))
    ap.add_argument("--interval", type=float, default=float(env("AGENT_INTERVAL", 5)))
    a = ap.parse_args()
    if not a.token:
        raise SystemExit("AGENT_TOKEN / --token is required")
    if a.serve:
        serve(a.host, a.port, a.token)
    else:
        push(a.server, a.token, a.name, a.interval)


if __name__ == "__main__":
    main()

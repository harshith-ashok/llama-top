# 🦙 llama-top

Open-source control plane for AI inference infrastructure: monitor hosts, Ollama and
OpenAI-compatible servers, and record per-request token/latency analytics. See
[ai-infrastructure-dashboard-features.md](ai-infrastructure-dashboard-features.md) for the full roadmap.

**Status: Phase 1 (core monitoring).** Deployed only via Docker.

## Quick start (Windows, macOS, Linux)

Requires [Docker](https://docs.docker.com/get-docker/) with Compose v2.

```bash
git clone <this repo> && cd llama-top
docker compose up -d --build
```

Open <http://localhost:3000>. If Ollama is running on your machine (port 11434) it is registered
automatically as **Local Ollama**; add other servers on the **Sources** page.

```bash
docker compose logs -f      # logs
docker compose down         # stop (data is kept in the llamatop-data volume)
docker compose down -v      # stop and delete all data
```

Copy [.env.example](.env.example) to `.env` to change the port, bind address, retention, etc.

## What's in Phase 1

| Area | Details |
| --- | --- |
| Source registry | Add / edit / disable / remove Ollama and OpenAI-compatible sources, health, latency, capability detection, tags |
| Model inventory | Cross-source list, loaded state and VRAM (Ollama `/api/tags` + `/api/ps`), digest mismatch flag |
| Host monitoring | CPU, memory, disk, network, processes, NVIDIA GPU/VRAM/power/temp (when available), history charts |
| Request tracking | Recording gateway: tokens, tok/s, TTFT, latency, finish reason, errors, app/session attribution |
| Analytics | Token and speed trends, per-model comparison, error rate |

## Recording requests (the gateway)

A monitoring dashboard cannot see traffic that goes directly to a provider, so route clients through the
gateway URL shown on the **Sources** page:

| Client type | Base URL |
| --- | --- |
| Ollama | `http://localhost:3000/gateway/<source-id>` |
| OpenAI-compatible | `http://localhost:3000/gateway/<source-id>` (the source's base URL already includes `/v1`) |

Streaming is passed through unbuffered. Optional headers `X-LlamaTop-App` and `X-LlamaTop-Session` attribute
requests to an application/session. Only metadata is stored — **prompts and responses are never recorded.**
For streamed OpenAI responses, token counts appear only if the client sets `stream_options.include_usage`.

## Host metrics for remote machines (e.g. a Windows PC over Tailscale)

Ollama's API cannot report CPU/RAM/GPU for the machine it runs on, so install the small **host agent** there.
The dashboard *pulls* from it, so the dashboard itself never needs to be exposed to your tailnet. For real
hardware numbers run the agent natively (Docker on Windows/macOS would only see its own VM).

On the remote machine (Python 3.11+, with a clone of this repo):

```powershell
pip install .\backend
llamatop-agent --serve --token <a-long-random-secret> --host 100.74.98.40 --port 9100
# allow the port on the Tailscale interface (run once, as Administrator)
New-NetFirewallRule -DisplayName "llama-top agent" -Direction Inbound -Protocol TCP -LocalPort 9100 -RemoteAddress 100.64.0.0/10 -Action Allow
```

Bind `--host` to the machine's Tailscale IP so it is not reachable on other networks. To start it at logon:

```powershell
schtasks /Create /TN llamatop-agent /SC ONLOGON /RL HIGHEST /TR "llamatop-agent --serve --token <secret> --host 100.74.98.40"
```

Then in the dashboard, open **Sources → Add source** (or the server icon on an existing source), and fill in
*Host agent URL* `http://100.74.98.40:9100` and the token. The machine appears on the **Host** page with CPU,
memory, disk, network, processes and NVIDIA GPU/VRAM history (GPU needs NVIDIA drivers on that machine).
The agent only exposes read-only metrics; there is no remote command execution.

A Linux box can use the same command, or `docker compose --profile agent up -d agent` in push mode
(`AGENT_TOKEN` and `LLAMATOP_SERVER` in `.env`; the dashboard must then be reachable from that machine).

## Docker-specific notes

- **macOS / Windows:** Docker runs in a Linux VM, so the built-in Host page reports that VM's CPU/RAM, not the
  physical machine, and cannot see Apple/AMD/Intel GPUs. Ollama on the host is reached via `host.docker.internal`.
- **NVIDIA GPU telemetry (Linux / WSL2):** install `nvidia-container-toolkit`, then
  `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build`.
- **Security:** the UI binds to `127.0.0.1` by default and has no login yet. Don't expose it to untrusted networks
  (`LLAMATOP_BIND=0.0.0.0`) without a reverse proxy providing authentication. Source API keys are stored in the
  database (never returned by the API).

## Development

Everything runs in containers for users, but contributors can run the pieces natively:

```bash
# backend (Python 3.11+)
cd backend && python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" && pytest && ruff check .
uvicorn app.main:app --reload

# frontend (Node 22+), proxies /api to localhost:8000
cd front && npm ci && npm run dev
npm run lint && npm run typecheck && npm test && npm run build
```

Stack: FastAPI + SQLAlchemy/SQLite, React + TypeScript, Tailwind CSS v4, shadcn/ui, Apache ECharts.

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every push/PR: backend lint + tests and frontend
lint/typecheck/tests/build on **Ubuntu, macOS and Windows**, then builds the Docker images and smoke-tests the
running compose stack.

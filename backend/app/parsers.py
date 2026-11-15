"""Incremental parsing of provider responses into normalized usage metrics.

Ollama streams NDJSON; OpenAI-compatible servers stream SSE (``data: {...}``) or
return a single JSON document. The parser is fed raw bytes as they pass through the
gateway and never alters them.
"""

from __future__ import annotations

import json
import time
from typing import Any

MAX_BUFFER = 8 * 1024 * 1024


def classify(path: str) -> str | None:
    """Return the logical operation for a request path, or None if not inference."""
    p = path.strip("/")
    for suffix, kind in (
        ("api/chat", "chat"),
        ("api/generate", "generate"),
        ("api/embed", "embed"),
        ("api/embeddings", "embed"),
        ("chat/completions", "chat"),
        ("completions", "generate"),
        ("embeddings", "embed"),
    ):
        if p.endswith(suffix):
            return kind
    return None


def request_info(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    params: dict[str, Any] = {}
    opts = data.get("options")
    if isinstance(opts, dict):
        params.update(opts)
    for k in ("temperature", "top_p", "seed", "max_tokens", "max_completion_tokens", "num_ctx"):
        if k in data:
            params[k] = data[k]
    return {"model": data.get("model"), "stream": bool(data.get("stream")), "params": params}


class UsageParser:
    def __init__(self, started: float, ollama: bool) -> None:
        self.started = started
        self.ollama = ollama
        self.ttft_ms: float | None = None
        self.usage: dict[str, Any] = {}
        self.finish_reason: str | None = None
        self.error: str | None = None
        self._buf = b""
        self._body = bytearray()
        self._sse = False

    def feed(self, chunk: bytes, content_type: str = "") -> None:
        if "event-stream" in content_type:
            self._sse = True
        if len(self._body) < MAX_BUFFER:
            self._body += chunk
        if not (self.ollama or self._sse):
            return
        self._buf += chunk
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            self._line(line.strip())

    def _line(self, line: bytes) -> None:
        if not line:
            return
        if line.startswith(b"data:"):
            line = line[5:].strip()
        if line == b"[DONE]":
            return
        try:
            obj = json.loads(line)
        except ValueError:
            return
        if isinstance(obj, dict):
            self._chunk(obj)

    def _chunk(self, obj: dict[str, Any]) -> None:
        if "error" in obj and not self.error:
            err = obj["error"]
            self.error = err.get("message") if isinstance(err, dict) else str(err)
        if self.ollama:
            text = (obj.get("message") or {}).get("content") or obj.get("response")
            if text and self.ttft_ms is None:
                self.ttft_ms = (time.monotonic() - self.started) * 1000
            if obj.get("done"):
                self.usage = {
                    k: obj[k]
                    for k in (
                        "prompt_eval_count",
                        "eval_count",
                        "prompt_eval_duration",
                        "eval_duration",
                        "load_duration",
                        "total_duration",
                    )
                    if k in obj
                }
                self.finish_reason = obj.get("done_reason") or self.finish_reason
            return
        for choice in obj.get("choices") or []:
            delta = choice.get("delta") or {}
            text = delta.get("content") or delta.get("reasoning_content") or choice.get("text")
            if text and self.ttft_ms is None:
                self.ttft_ms = (time.monotonic() - self.started) * 1000
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
        if isinstance(obj.get("usage"), dict):
            self.usage = obj["usage"]

    def finish(self) -> dict[str, Any]:
        """Flush and return normalized metrics. Raw provider usage is kept verbatim."""
        if not (self.ollama or self._sse):
            try:
                doc = json.loads(bytes(self._body))
            except ValueError:
                doc = None
            if isinstance(doc, dict):
                self._chunk(doc)
        elif self._buf.strip():
            self._line(self._buf.strip())
        return normalize(self.usage, self.ollama, self.ttft_ms, self.finish_reason, self.error)


def _tps(count: Any, duration_ns: Any) -> float | None:
    if (
        isinstance(count, (int, float))
        and isinstance(duration_ns, (int, float))
        and duration_ns > 0
    ):
        return count / (duration_ns / 1_000_000_000)
    return None


def normalize(
    usage: dict[str, Any],
    ollama: bool,
    ttft_ms: float | None,
    finish_reason: str | None,
    error: str | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "prompt_tokens": None,
        "completion_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
        "gen_tps": None,
        "prompt_tps": None,
        "load_ms": None,
        "ttft_ms": ttft_ms,
        "finish_reason": finish_reason,
        "error": error,
        "raw_usage": usage,
    }
    if ollama:
        out["prompt_tokens"] = usage.get("prompt_eval_count")
        out["completion_tokens"] = usage.get("eval_count")
        out["gen_tps"] = _tps(usage.get("eval_count"), usage.get("eval_duration"))
        out["prompt_tps"] = _tps(usage.get("prompt_eval_count"), usage.get("prompt_eval_duration"))
        if isinstance(usage.get("load_duration"), (int, float)):
            out["load_ms"] = usage["load_duration"] / 1_000_000
    else:
        out["prompt_tokens"] = usage.get("prompt_tokens") or usage.get("input_tokens")
        out["completion_tokens"] = usage.get("completion_tokens") or usage.get("output_tokens")
        details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        out["cached_tokens"] = details.get("cached_tokens")
        cdetails = usage.get("completion_tokens_details") or {}
        out["reasoning_tokens"] = cdetails.get("reasoning_tokens")
    return out

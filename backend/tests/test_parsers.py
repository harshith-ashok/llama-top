import json
import time

from app.parsers import UsageParser, classify, request_info


def test_classify():
    assert classify("api/chat") == "chat"
    assert classify("v1/chat/completions") == "chat"
    assert classify("chat/completions") == "chat"
    assert classify("v1/embeddings") == "embed"
    assert classify("api/tags") is None


def test_request_info():
    info = request_info(
        json.dumps(
            {"model": "m", "stream": True, "options": {"seed": 1}, "temperature": 0.2}
        ).encode()
    )
    assert info == {"model": "m", "stream": True, "params": {"seed": 1, "temperature": 0.2}}
    assert request_info(b"not json") == {}


def test_ollama_stream_metrics():
    p = UsageParser(time.monotonic(), ollama=True)
    lines = [
        {"message": {"content": "Hi"}, "done": False},
        {
            "message": {"content": ""},
            "done": True,
            "done_reason": "stop",
            "eval_count": 50,
            "eval_duration": 2_000_000_000,
            "prompt_eval_count": 10,
            "prompt_eval_duration": 500_000_000,
            "load_duration": 3_000_000,
            "total_duration": 1,
        },
    ]
    blob = ("\n".join(json.dumps(x) for x in lines) + "\n").encode()
    p.feed(blob[:20])  # split mid-line to exercise buffering
    p.feed(blob[20:])
    m = p.finish()
    assert m["completion_tokens"] == 50 and m["prompt_tokens"] == 10
    assert m["gen_tps"] == 25.0 and m["prompt_tps"] == 20.0
    assert m["load_ms"] == 3.0 and m["finish_reason"] == "stop"
    assert m["ttft_ms"] is not None
    assert m["raw_usage"]["eval_count"] == 50


def test_openai_sse_usage():
    p = UsageParser(time.monotonic(), ollama=False)
    chunks = [
        {"choices": [{"delta": {"content": "a"}}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}]},
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 3,
                "prompt_tokens_details": {"cached_tokens": 4},
                "completion_tokens_details": {"reasoning_tokens": 1},
            },
        },
    ]
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    p.feed(body.encode(), "text/event-stream")
    m = p.finish()
    assert (m["prompt_tokens"], m["completion_tokens"]) == (7, 3)
    assert m["cached_tokens"] == 4 and m["reasoning_tokens"] == 1
    assert m["finish_reason"] == "length" and m["gen_tps"] is None


def test_openai_non_stream():
    p = UsageParser(time.monotonic(), ollama=False)
    p.feed(
        json.dumps(
            {
                "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
            }
        ).encode(),
        "application/json",
    )
    m = p.finish()
    assert m["completion_tokens"] == 2 and m["finish_reason"] == "stop"

"""OpenAI-compatible mock LLM server for load testing.

The 50-user Locust run cannot hit a real cloud LLM (free-tier rate
limits would 429 immediately and pollute every percentile), so the app
is pointed at this server instead via `LLM_BASE_URL`. It speaks just
enough of the OpenAI chat-completions protocol for the app's
`OpenAICompatibleLLMService` adapter: a JSON completion, and an SSE
token stream ending with the `CONFIDENCE:` marker line the streaming
prompt contract expects.

Responses are canned but delivery is realistically paced (delays match
what we measured against real Groq in Phases 3-4: ~0.25s to first
token, ~0.8s total), so the benchmark exercises the full production
path — auth, MiniLM query embedding, pgvector HNSW search, prompt
build, SSE framing — with only the token generation simulated.

Usage:
    python benchmarks/mock_llm.py          # serves on 127.0.0.1:9099

Then start the app with LLM_BASE_URL=http://127.0.0.1:9099/v1
"""

import asyncio
import json
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

# Pacing (seconds), overridable via env for experiments.
FIRST_TOKEN_DELAY = float(os.getenv("MOCK_FIRST_TOKEN_DELAY", "0.25"))
INTER_CHUNK_DELAY = float(os.getenv("MOCK_INTER_CHUNK_DELAY", "0.02"))
NONSTREAM_DELAY = float(os.getenv("MOCK_NONSTREAM_DELAY", "0.75"))

MOCK_ANSWER = (
    "According to the uploaded documents, the requested figure is "
    "approximately 42 units, reported in the annual summary. The "
    "surrounding context attributes the change to seasonal demand and "
    "notes that the methodology matches the previous reporting period."
)

app = FastAPI(title="mock-llm")


def _completion_body(model: str) -> dict:
    # Non-streaming callers use the grounded JSON contract:
    # message.content is itself a JSON object with answer + confidence.
    content = json.dumps({"answer": MOCK_ANSWER, "confidence": "HIGH"})
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _chunk(model: str, text: str) -> str:
    body = {
        "id": "chatcmpl-mock",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
    }
    return f"data: {json.dumps(body)}\n\n"


async def _token_stream(model: str):
    # Streaming callers use the plain-text-plus-marker contract.
    words = MOCK_ANSWER.split(" ")
    await asyncio.sleep(FIRST_TOKEN_DELAY)
    for i, word in enumerate(words):
        text = word if i == len(words) - 1 else word + " "
        yield _chunk(model, text)
        await asyncio.sleep(INTER_CHUNK_DELAY)
    yield _chunk(model, "\nCONFIDENCE: HIGH")
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    model = payload.get("model", "mock")
    if payload.get("stream"):
        return StreamingResponse(_token_stream(model), media_type="text/event-stream")
    await asyncio.sleep(NONSTREAM_DELAY)
    return _completion_body(model)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9099, log_level="warning")

"""Locust load-test scenario: login -> chat against the eval corpus.

Each simulated user logs in as its own pre-seeded bench account
(benchmarks/seed_users.py) inside the eval organization, so every
/chat request runs the full production path against a real-sized
index: JWT auth, MiniLM query embedding, pgvector HNSW search over
12,855 chunks, prompt build with history + summary memory, LLM call,
history writes.

The LLM must be the local mock (benchmarks/mock_llm.py) — point the
app at it with LLM_BASE_URL=http://127.0.0.1:9099/v1. Percentiles
therefore measure OUR stack with token generation simulated at
realistic pacing, not cloud LLM latency (that is measured separately
by benchmarks/streaming_ttft.py).

Questions are sampled from the answerable half of the Phase 5 golden
set so retrieval does real work (matching documents exist).

Run (after seeding users, starting the mock and the app):
    locust -f benchmarks/locustfile.py --host http://127.0.0.1:8000 \
        --users 50 --spawn-rate 5 --run-time 3m --headless \
        --csv benchmarks/results/load
"""

import json
import random
import time
from itertools import count
from pathlib import Path

from locust import HttpUser, between, task

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "evals" / "golden_qa.jsonl"

BENCH_EMAIL_TEMPLATE = "bench-{i:03d}@example.com"
BENCH_PASSWORD = "bench-password"
BENCH_USER_COUNT = 50  # keep in sync with seed_users.py --count

FALLBACK_QUESTIONS = [
    "What does the annual summary report about seasonal demand?",
    "Which methodology was used in the previous reporting period?",
]


def load_questions() -> list[str]:
    if not GOLDEN_PATH.exists():
        return FALLBACK_QUESTIONS
    questions = []
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("type") == "answerable":
                questions.append(item["question"])
    return questions or FALLBACK_QUESTIONS


QUESTIONS = load_questions()

_next_user_index = count(1)


class ChatUser(HttpUser):
    # Think time between actions: a person reading the answer before
    # asking the next question.
    wait_time = between(1, 3)

    def on_start(self):
        i = (next(_next_user_index) - 1) % BENCH_USER_COUNT + 1
        email = BENCH_EMAIL_TEMPLATE.format(i=i)
        response = self.client.post(
            "/auth/login",
            data={"username": email, "password": BENCH_PASSWORD},
            name="/auth/login",
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {token}"

    @task(3)
    def chat(self):
        self.client.post(
            "/chat",
            json={"question": random.choice(QUESTIONS), "top_k": 5},
            name="/chat",
        )

    @task(1)
    def chat_stream(self):
        """SSE endpoint: Locust's own timing for a streaming response
        stops at the headers, so first-token and full-stream times are
        reported as custom entries via the request event."""
        payload = {"question": random.choice(QUESTIONS), "top_k": 5}
        start = time.perf_counter()
        with self.client.post(
            "/chat/stream",
            json=payload,
            stream=True,
            catch_response=True,
            name="/chat/stream (headers)",
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            ttft_ms = None
            received = 0
            for line in response.iter_lines():
                received += len(line)
                if ttft_ms is None and line.startswith(b"event: token"):
                    ttft_ms = (time.perf_counter() - start) * 1000
                    self.environment.events.request.fire(
                        request_type="SSE",
                        name="/chat/stream (first token)",
                        response_time=ttft_ms,
                        response_length=0,
                        exception=None,
                        context={},
                    )
            total_ms = (time.perf_counter() - start) * 1000
            self.environment.events.request.fire(
                request_type="SSE",
                name="/chat/stream (complete)",
                response_time=total_ms,
                response_length=received,
                exception=None,
                context={},
            )
            response.success()

    @task(1)
    def list_documents(self):
        self.client.get("/documents", name="/documents")

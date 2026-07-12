"""Streaming time-to-first-token against the REAL cloud LLM.

The 50-user Locust run uses a mock LLM (free-tier rate limits make a
real one impossible at that load), so this companion script measures
the one number the mock cannot: honest end-to-end time-to-first-token
with the production Groq model in the loop. It runs sequentially at
low volume — ~20 requests, paced — staying far under free-tier limits.

Start the app WITHOUT LLM_BASE_URL (so it talks to real Groq), then:
    python benchmarks/streaming_ttft.py --requests 20

Writes benchmarks/results/streaming_ttft.json.
"""

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "evals" / "golden_qa.jsonl"
RESULTS_PATH = REPO_ROOT / "benchmarks" / "results" / "streaming_ttft.json"

BASE_URL = "http://127.0.0.1:8000"
BENCH_EMAIL = "bench-001@example.com"
BENCH_PASSWORD = "bench-password"
PACE_SECONDS = 2.0  # stay well under free-tier requests/minute


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(pct / 100 * (len(ordered) + 1)) - 1)
    return ordered[max(idx, 0)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=20)
    args = parser.parse_args()

    questions = [
        json.loads(line)["question"]
        for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["type"] == "answerable"
    ]
    random.seed(42)  # same question sample every run
    sample = random.sample(questions, min(args.requests, len(questions)))

    login = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": BENCH_EMAIL, "password": BENCH_PASSWORD},
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    ttfts: list[float] = []
    totals: list[float] = []
    for n, question in enumerate(sample, 1):
        start = time.perf_counter()
        response = requests.post(
            f"{BASE_URL}/chat/stream",
            json={"question": question, "top_k": 5},
            headers=headers,
            stream=True,
            timeout=60,
        )
        response.raise_for_status()
        ttft = None
        for line in response.iter_lines():
            if ttft is None and line.startswith(b"event: token"):
                ttft = (time.perf_counter() - start) * 1000
        total = (time.perf_counter() - start) * 1000
        ttfts.append(ttft if ttft is not None else total)
        totals.append(total)
        print(f"{n:>3}/{len(sample)}  ttft={ttft:7.0f}ms  total={total:7.0f}ms")
        time.sleep(PACE_SECONDS)

    stats = {
        "requests": len(sample),
        "concurrency": 1,
        "ttft_ms": {
            "p50": round(statistics.median(ttfts)),
            "p95": round(percentile(ttfts, 95)),
            "min": round(min(ttfts)),
            "max": round(max(ttfts)),
        },
        "total_ms": {
            "p50": round(statistics.median(totals)),
            "p95": round(percentile(totals, 95)),
            "min": round(min(totals)),
            "max": round(max(totals)),
        },
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

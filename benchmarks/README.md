# Benchmarks — load test & latency

Measured on 2026-07-12: a 50-concurrent-user Locust run against the
full stack, plus a real-cloud-LLM time-to-first-token measurement.
Raw artifacts: [results/load_stats.csv](results/load_stats.csv),
[results/streaming_ttft.json](results/streaming_ttft.json).

## Setup (read this before quoting numbers)

A cloud LLM cannot sit inside a 50-user load test on a free tier —
rate limits would 429 immediately and the retries would poison every
percentile. So the load test splits the measurement in two:

1. **Load test (mock LLM)** — the app runs with `LLM_BASE_URL` pointed
   at `benchmarks/mock_llm.py`, a local OpenAI-compatible server that
   returns canned tokens paced to match what we measured against real
   Groq (~0.25 s to first token, ~0.75 s full completion). Everything
   else is real: JWT auth, bcrypt login, MiniLM query embedding (CPU),
   pgvector HNSW search over the 12,855-chunk Phase 5 eval corpus,
   history + summary-memory reads, prompt build, SSE framing, history
   writes. The percentiles measure **our stack under concurrency**,
   with token generation simulated.
2. **TTFT run (real Groq)** — 20 sequential paced requests through
   `/chat/stream` with the production model (`llama-3.3-70b-versatile`)
   actually in the loop, measuring honest end-to-end time-to-first-token
   at low load.

Each of the 50 simulated users logs in as its own seeded account
(`benchmarks/seed_users.py`) inside the eval org, and asks questions
sampled from the Phase 5 golden set — so retrieval does real work
against a real-sized index and returns real matching documents.

## Load test results (50 users, mock LLM)

Config: Locust 2.45.0, 50 users, spawn rate 5/s, 3 minutes, think time
1–3 s per user; uvicorn with **4 workers**; Postgres + Redis in Docker;
everything (Locust, app, DB, mock) on one Windows laptop.

**4,360 requests · 24.3 req/s sustained · 0 failures**

| endpoint | p50 | p95 | p99 | notes |
|---|---:|---:|---:|---|
| `POST /chat` | 880 ms | 1,100 ms | 1,300 ms | includes 750 ms simulated LLM → **~130 ms p50 stack overhead** |
| `POST /chat/stream` — first token | 490 ms | 680 ms | 910 ms | includes ~380 ms simulated LLM pacing¹ |
| `POST /chat/stream` — complete | 1,300 ms | 1,600 ms | 1,800 ms | full SSE stream, 33 token events |
| `GET /documents` | 31 ms | 61 ms | 260 ms | plain DB read under the same load |
| `POST /auth/login` | 470 ms | 660 ms | 1,500 ms | dominated by bcrypt — intentional |

¹ 250 ms mock first-token delay + ~130 ms of 20 ms/chunk pacing before
the 40-char streaming holdback releases the first client event.

Subtracting the constant mock pacing, the platform itself (auth →
embed → HNSW search over 12,855 vectors → memory reads → prompt →
SSE) holds **~130–150 ms median overhead at 50 concurrent users with
zero errors** — retrieval is nowhere near the bottleneck; the LLM is.

## Real-LLM streaming TTFT (Groq, low concurrency)

20 sequential requests, 2 s pacing, production model, top_k=5:

| metric | p50 | p95 | min | max |
|---|---:|---:|---:|---:|
| time to first token | **318 ms** | 692 ms | 260 ms | 692 ms |
| full response | 374 ms | 1,028 ms | 299 ms | 1,028 ms |

## Reproduce

```bash
python benchmarks/seed_users.py                    # once

# terminal 1 — mock LLM
python benchmarks/mock_llm.py

# terminal 2 — app pointed at the mock (PowerShell syntax)
$env:LLM_BASE_URL='http://127.0.0.1:9099/v1'
uvicorn app.main:app --workers 4 --log-level warning

# terminal 3 — the load test
locust -f benchmarks/locustfile.py --host http://127.0.0.1:8000 \
    --users 50 --spawn-rate 5 --run-time 3m --headless \
    --csv benchmarks/results/load

# real-Groq TTFT: restart uvicorn WITHOUT LLM_BASE_URL, then
python benchmarks/streaming_ttft.py --requests 20
```

Afterwards, clear the summary tasks the bench chats queued (the Celery
worker isn't running during the test, so they pile up in Redis):

```bash
docker exec rag-redis redis-cli DEL rag-queue
```

## Limitations

- **One machine**: Locust, the app, Postgres, Redis, and the mock all
  shared a laptop, so the load generator competes with the system
  under test. Numbers are conservative rather than flattering, but a
  proper rig would isolate them.
- **Mock pacing is constant** (0.25 s / 0.75 s per request); a real
  provider has variance and tail latency the load test doesn't model.
  That's exactly why the mock-LLM percentiles are reported as *stack*
  latency, never as end-to-end product latency.
- **Single 3-minute run**, no variance across runs; TTFT is n=20 at
  concurrency 1.
- The `/chat/stream (headers)` rows in the raw CSV measure only
  time-to-response-headers (FastAPI sends SSE headers before the
  generator runs) — use the *first token* metric, not that one.

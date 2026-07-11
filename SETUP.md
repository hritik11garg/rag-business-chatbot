# 🛠 Project Setup Guide (Fresh Clone)

Step-by-step instructions to get the RAG Business Chatbot running on a
new machine after `git clone`.

**Stack:** FastAPI · PostgreSQL + pgvector · Redis + Celery · Pluggable LLM (OpenAI / Groq / Gemini / Ollama / Claude) · Sentence Transformers

---

## Prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | 3.11+ | `python --version` |
| Docker Desktop | any recent | `docker --version` (must be running) |
| Git | any | `git --version` |

You also need an API key for ONE LLM provider — the free Groq tier
works fine (see the provider table in step 3).

---

## 1. Create and activate a virtual environment

From the project root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> On Linux/macOS: `python3 -m venv venv && source venv/bin/activate`

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

---

## 2. Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements/base.txt
```

Optional extras:

```powershell
pip install -r requirements/test.txt   # pytest
pip install -r requirements/dev.txt    # black, ruff, mypy, ipython, fpdf2 (eval corpus)
```

> ⚠️ This installs `torch` and `sentence-transformers` — the download is
> several GB and can take a while.

---

## 3. Create your `.env` file

Copy the example and fill in real values:

```powershell
Copy-Item .env.example .env
```

Edit `.env` so it matches the Docker database credentials below:

```env
ENV=development
SECRET_KEY=<any-long-random-string>
DATABASE_URL=postgresql://raguser:ragpass@localhost:5433/ragdb

# Pick ONE provider: openai | groq | gemini | ollama | anthropic
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_<your-real-key>
```

Set the API key that matches your provider — `OPENAI_API_KEY`,
`GROQ_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY`
(`ollama` runs locally and needs no key). Where to get a free key:

| Provider | Key page | Notes |
|---|---|---|
| `groq` | console.groq.com | Free tier, very fast Llama models |
| `gemini` | aistudio.google.com | Free tier |
| `ollama` | — (install from ollama.com, then `ollama pull llama3.2`) | Fully local |
| `openai` | platform.openai.com | Paid |
| `anthropic` | console.anthropic.com | Paid (Claude) |

Optional `.env` overrides: `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TEMPERATURE`
(defaults per provider live in `app/infrastructure/llm/factory.py`).

Generate a good SECRET_KEY:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

> 🔒 `.env` is gitignored — never commit it.

---

## 4. Start Postgres (pgvector) and Redis

Both services are defined in `docker-compose.yml`:

```powershell
docker compose up -d
```

This starts:

- **rag-postgres** — PostgreSQL with pgvector, on port **5433**
- **rag-redis** — Redis (Celery broker), on port **6379**

Verify both are running:

```powershell
docker ps
```

---

## 5. Enable the pgvector extension

Nothing to do — the initial Alembic migration runs
`CREATE EXTENSION IF NOT EXISTS vector` before creating tables.

(To enable it manually anyway:
`docker exec rag-postgres psql -U raguser -d ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"`)

---

## 6. Create the database tables

```powershell
alembic upgrade head
```

Expected tables: `users`, `organizations`, `documents`,
`document_embeddings`, `chat_history`, `conversation_summaries`
(plus Alembic's own `alembic_version`).

---

## 7. Run the application

Open **two terminals**, both with the venv activated (`.\venv\Scripts\Activate.ps1`).

**Terminal 1 — Celery worker** (background FAQ generation):

```powershell
celery -A app.core.celery_app:celery worker --pool=solo -Q rag-queue --loglevel=info
```

**Terminal 2 — FastAPI server:**

```powershell
uvicorn app.main:app --reload
```

Open Swagger UI: **http://127.0.0.1:8000/docs**

Quick health check: http://127.0.0.1:8000/health → `{"status": "ok"}`

---

## 8. First-use flow (in Swagger)

1. `POST /auth/signup` — create an organization + first user
2. `POST /auth/login` — get a JWT token, click **Authorize** 🔒 and paste it
3. `POST /documents/upload` — upload a PDF (stored under `uploads/org_<id>/`)
4. `POST /chat` — ask questions about your documents

---

## 9. Run the tests

```powershell
pip install -r requirements/test.txt
pytest
```

---

## 10. (Optional) Reproduce the evals

The measured RAG-vs-vanilla results in [evals/README.md](evals/README.md)
can be regenerated with the five commands listed there (corpus fetch →
bulk ingest → golden set → answers → judge). Requires
`LLM_PROVIDER=groq` and `pip install -r requirements/dev.txt` (fpdf2).
The stages checkpoint per item, so free-tier rate limits can interrupt
them safely — rerun the same command to resume.

---

## Daily startup (after first setup)

```powershell
docker compose up -d
.\venv\Scripts\Activate.ps1
# terminal 1:
celery -A app.core.celery_app:celery worker --pool=solo -Q rag-queue --loglevel=info
# terminal 2:
uvicorn app.main:app --reload
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `connection refused` on DB | Docker not running, or postgres not up — `docker compose up -d`, check `docker logs rag-postgres` |
| `type "vector" does not exist` | Step 5 was skipped — enable the pgvector extension |
| Tables missing / `relation does not exist` | Step 6 was skipped — run `alembic upgrade head` |
| Celery tasks never run | Redis not running, or worker not started with `-Q rag-queue` |
| LLM auth error / `RuntimeError: ... is not set` | The API key matching `LLM_PROVIDER` is missing/wrong in `.env` |
| Port 5433 or 6379 already in use | Stop the conflicting service or change the port mapping in `docker-compose.yml` |
| Slow first chat/upload | Normal — sentence-transformers downloads the MiniLM model on first use |

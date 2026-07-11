# 📚 Enterprise Business Knowledge Base Chatbot (RAG)

A production-style Retrieval Augmented Generation (RAG) system that
allows organizations to upload internal documents (PDFs) and interact
with them through an AI chatbot powered by semantic search, vector
embeddings, background workers, and cloud LLMs.

Built **from scratch — no LangChain** — combining document ingestion,
embeddings, pgvector similarity search, async workers, and grounded
LLM responses, the way modern enterprise AI assistants in SaaS
platforms and internal knowledge tools are built.

**Stack:** FastAPI · PostgreSQL + pgvector · Redis + Celery · Sentence Transformers (MiniLM) · Pluggable LLM (OpenAI / Groq / Gemini / Ollama / Claude) · SQLAlchemy + Alembic · Docker

------------------------------------------------------------------------

# 🚀 Core Capabilities

- Multi-tenant architecture (organization-isolated data at every query)
- JWT authentication (OAuth2 password flow)
- Organization-scoped PDF uploads with integrity validation
- Duplicate filename versioning (safe re-uploads)
- Automatic text extraction, cleaning, and overlapping chunking
- Sentence Transformer embeddings (all-MiniLM-L6-v2, 384-dim)
- pgvector semantic similarity search
- pgvector semantic similarity search with an HNSW index, configurable
  top-k, and optional per-document filtering
- Intent routing — chitchat handled instantly, knowledge questions go
  through the full RAG pipeline
- Synthetic FAQ generation as a Celery background task (retrieval boost)
- Two-tier conversational memory: recent history in the prompt + a
  rolling LLM-maintained summary updated asynchronously off the
  request path
- Grounded answers with source citations via a **pluggable LLM layer**
  — switch between OpenAI, Groq, Gemini, local Ollama, or Claude with
  one `.env` variable (`LLM_PROVIDER`)
- **SSE streaming** endpoint (`/chat/stream`) with time-to-first-token
  ~0.25s vs ~0.33s full response
- LLM-graded confidence score (high / medium / low) on every response,
  from the same call as the answer (no second round-trip)
- Centralized prompt templates + response parsers (`app/prompts/`)
- Document deletion with vector + file cleanup
- Alembic database migrations
- **Held-out eval harness with committed results** — see
  [Measured results](#-measured-results) below
- Pytest test suite (22 tests) for chat, streaming, and schemas

------------------------------------------------------------------------

# 🧠 High-Level System Architecture

                      ┌────────────────────┐
                      │     User / Org     │
                      └─────────┬──────────┘
                                │
                                ▼
                      ┌────────────────────┐
                      │   FastAPI Backend  │
                      └─────────┬──────────┘
                                │
            ┌───────────────────┼────────────────────┐
            ▼                   ▼                    ▼
     ┌──────────────┐   ┌───────────────┐    ┌────────────────┐
     │Postgres DB   │   │pgvector Index │    │LLM Provider    │
     │(users/docs)  │   │(embeddings)   │    │(cloud or local)│
     └──────────────┘   └───────────────┘    └────────────────┘
                                │
                                ▼
                       ┌────────────────────┐
                       │ Redis + Celery     │
                       │ Async Workers      │
                       └────────────────────┘

------------------------------------------------------------------------

# 🏛 Code Architecture (SOLID / Hexagonal)

The codebase follows a layered, dependency-inverted design:

    app/
    ├── api/             # FastAPI routes, schemas, auth dependencies
    ├── domain/          # Protocols (LLMService, EmbeddingService,
    │                    #   ChatHistoryRepository, IntentClassifier)
    ├── infrastructure/  # Implementations: LLM adapters + provider
    │                    #   factory, Sentence Transformers, chat history
    ├── use_cases/       # Business logic: chat routing, RAG chat,
    │                    #   upload, delete, signup, chitchat
    ├── composition/     # Dependency wiring (composition root)
    ├── services/        # Document processing, embedding store/search,
    │                    #   confidence scoring, FAQ generation
    ├── tasks/           # Celery background tasks
    ├── db/              # SQLAlchemy models + session
    └── core/            # Settings, security (JWT/bcrypt), Celery app

Use cases depend on **Protocols**, not concrete providers. The LLM
layer proves it: one OpenAI-compatible adapter serves OpenAI, Groq,
Gemini, and Ollama; a second adapter serves Claude — and a factory
picks one from `LLM_PROVIDER`, with zero changes to business logic.

------------------------------------------------------------------------

# 🏗 Pipelines

## Document Upload Pipeline

1.  User uploads a PDF under their organization
2.  Backend validates PDF integrity & format
3.  Duplicate filenames auto-versioned
4.  File stored in an org-specific folder (`uploads/org_<id>/`)
5.  Metadata saved to Postgres
6.  Text extracted (pypdf), normalized, and split into overlapping chunks
7.  Chunk embeddings generated via MiniLM and stored in pgvector
8.  Celery task generates synthetic FAQs, embedded & stored for
    retrieval boosting

## Chat Pipeline

1.  Intent classified — greetings get an instant chitchat reply
2.  Knowledge questions are embedded via MiniLM
3.  Similarity search over the organization's embeddings (HNSW,
    configurable `top_k`, optional `document_ids` filter)
4.  Recent chat history + rolling conversation summary loaded
5.  Prompt constructed from context + memory (`app/prompts/`)
6.  Grounded answer generated by the configured LLM provider —
    buffered (`/chat`) or token-streamed over SSE (`/chat/stream`)
7.  Response returns the **answer**, **source filenames**, and an
    LLM-evaluated **confidence score**

------------------------------------------------------------------------

# 🔌 API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Create an organization + first user |
| `POST` | `/auth/login` | OAuth2 login → JWT access token |
| `GET` | `/me` | Current authenticated user |
| `GET` | `/documents` | List the organization's documents |
| `POST` | `/documents/upload` | Upload a PDF (triggers full RAG ingestion) |
| `DELETE` | `/documents/{id}` | Delete a document + its vectors + file |
| `POST` | `/chat` | Ask a question (RAG answer + sources + confidence) |
| `POST` | `/chat/stream` | Same, streamed as SSE token events |
| `GET` | `/health` | Health check |

Interactive docs: **http://127.0.0.1:8000/docs**

------------------------------------------------------------------------

# 🐘 Database Schema

  Table                 Purpose
  --------------------- -------------------------------------
  users                 Organization users & authentication
  organizations         Multi-tenant isolation
  documents             Uploaded PDF metadata
  document_embeddings   Chunk vectors + FAQ vectors (384-dim, HNSW)
  chat_history          Conversation memory (recent turns)
  conversation_summaries  Rolling per-user summary (long-term memory)

------------------------------------------------------------------------

# 🔍 Why pgvector Instead of Pinecone/FAISS?

- Fully local & open-source, embedded inside Postgres
- Vectors live next to the relational data they belong to —
  org-scoped filtering is a plain SQL `WHERE` clause
- No external SaaS dependency; production-safe & scalable

------------------------------------------------------------------------

# ⚙ Setup

**Full step-by-step guide: [SETUP.md](SETUP.md)** — includes
prerequisites, environment variables, database initialization, and
troubleshooting.

Quick version:

```bash
# 1. Environment
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements/base.txt
copy .env.example .env                             # then edit values

# 2. Infrastructure (Postgres + pgvector, Redis)
docker compose up -d

# 3. Database tables (the migration also enables the pgvector extension)
alembic upgrade head

# 4. Run (two terminals)
celery -A app.core.celery_app:celery worker --pool=solo -Q rag-queue --loglevel=info
uvicorn app.main:app --reload
```

> ⏱ First startup takes ~40s (torch / sentence-transformers imports),
> and the first embedding call downloads the MiniLM model.

Dependencies are split under `requirements/`:
`base.txt` (runtime) · `test.txt` (pytest) · `dev.txt` (black, ruff, mypy).

------------------------------------------------------------------------

# 🧪 Tests

```bash
pip install -r requirements/test.txt
pytest
```

22 tests covering the chat router (intent dispatch), the RAG chat use
case, streaming (confidence-marker holdback), request validation, and
prompt parsers — with fakes injected via the domain Protocols.

------------------------------------------------------------------------

# 📊 Measured results

Full method + numbers: **[evals/README.md](evals/README.md)**.
Highlights from a 100-question held-out eval (500 Wikipedia-article
PDFs ingested; graded by an independent LLM judge):

| metric | RAG | vanilla (same model, no retrieval) |
|---|---:|---:|
| correct on answerable questions (n=60) | **86.7%** | 33.3% |
| correct abstention on out-of-KB questions (n=40) | **97.5%** | 62.5% |
| overall hallucination rate | **2.0%** | 4.0% |

Ingestion throughput: **59.8 docs/min · 25.6 chunks/sec**
(12,855 chunks from 500 PDFs, single process, CPU MiniLM, zero failures).

------------------------------------------------------------------------

# 🗺 Roadmap

- ✅ Multi-provider LLM support (OpenAI / Groq / Gemini / Ollama / Claude)
- ✅ Startup-time model loading & HNSW vector indexing
- ✅ Configurable top-k retrieval + metadata filtering
- ✅ Prompt templating module
- ✅ SSE streaming responses + summary memory
- ✅ Held-out eval harness with committed results (see above)
- Load benchmarks (Locust), CI pipeline, structured logging, rate
  limiting, one-command Docker startup

------------------------------------------------------------------------

# 🏆 Enterprise Value

This project mirrors how companies build internal AI assistants,
customer support bots, private enterprise search, and knowledge
retrieval platforms.

Perfect for: ✔ Portfolio ✔ Freelancing ✔ Backend/AI Interviews

------------------------------------------------------------------------

# 👨‍💻 Author

Hritik Garg 🚀

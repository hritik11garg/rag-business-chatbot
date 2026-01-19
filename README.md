# 📚 Enterprise Business Knowledge Base Chatbot (RAG)

A production-style Retrieval Augmented Generation (RAG) system that
allows organizations to upload internal documents (PDFs) and interact
with them through an AI chatbot powered by semantic search, vector
embeddings, background workers, and cloud LLMs.

This project simulates how modern enterprise AI assistants used in SaaS
platforms, support portals, and internal knowledge tools are built ---
combining document ingestion, embeddings, vector databases, async
workers, and grounded LLM responses.

------------------------------------------------------------------------

# 🚀 Core Capabilities

-   Multi-tenant architecture (organization-isolated data)
-   JWT Authentication with secure login
-   Organization-scoped document uploads
-   Enterprise PDF validation
-   Duplicate filename versioning (safe re-uploads)
-   Automatic document chunking
-   Sentence Transformer embeddings (MiniLM)
-   pgvector semantic similarity search
-   Synthetic FAQ generation (Celery background)
-   Conversational chat memory
-   Cloud LLM answering via OpenAI API
-   Source citations with answers
-   Confidence scoring for every response
-   Background workers via Celery + Redis
-   Alembic database migrations
-   Document deletion with vector cleanup

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
     │Postgres DB   │   │pgvector Index │    │OpenAI LLM      │
     │(users/docs)  │   │(embeddings)   │    │(cloud)         │
     └──────────────┘   └───────────────┘    └────────────────┘
                                │
                                ▼
                       ┌────────────────────┐
                       │ Redis + Celery     │
                       │ Async Workers      │
                       └────────────────────┘

------------------------------------------------------------------------

# 🏗 Detailed Flow

## Document Upload Pipeline

1.  User uploads PDF under their organization
2.  Backend validates PDF integrity & format
3.  Duplicate filenames auto-versioned
4.  File stored in org-specific folder
5.  Metadata saved to Postgres
6.  Text extracted using PyPDF
7.  Text normalized & cleaned
8.  Document split into overlapping chunks
9.  Embeddings generated via MiniLM
10. Stored in pgvector with org scope
11. Celery task triggered for FAQ generation
12. FAQs embedded & stored for retrieval boost

------------------------------------------------------------------------

## Chat Pipeline

1.  User asks question
2.  Question embedded via MiniLM
3.  Similarity search within org embeddings
4.  Top chunks + FAQs retrieved
5.  Recent chat history loaded
6.  Prompt constructed with context + memory
7.  Sent to OpenAI API
8.  Grounded answer generated
9.  Response includes:
    -   Answer
    -   Sources
    -   Confidence score

------------------------------------------------------------------------

# 🐘 Database Usage

  Table                 Purpose
  --------------------- -------------------------------------
  users                 Organization users & authentication
  organizations         Multi-tenant isolation
  documents             Uploaded PDF metadata
  document_embeddings   Chunk vectors + FAQ vectors
  chat_history          Conversation memory

------------------------------------------------------------------------

# 🔁 Background Processing (Celery)

-   Handles heavy AI tasks asynchronously
-   Generates synthetic FAQs
-   Prevents blocking API requests
-   Runs independently from FastAPI
-   Uses Redis as broker
-   Production-style architecture pattern

------------------------------------------------------------------------

# 🔍 Why pgvector Instead of Pinecone?

-   Fully local & open-source
-   Embedded inside Postgres
-   No external SaaS dependency
-   Ideal for controlled enterprise RAG
-   Production-safe & scalable

------------------------------------------------------------------------

# 🤖 LLM Provider

Previously: Ollama (local inference) Now: OpenAI API (cloud production)

-   Faster
-   Better reasoning quality
-   Enterprise-standard architecture
-   Real SaaS-style deployment pattern

------------------------------------------------------------------------

# ⚙ Setup Requirements

## 1. Docker Postgres with pgvector

docker run -d\
--name rag-postgres\
-p 5433:5432\
-e POSTGRES_USER=raguser\
-e POSTGRES_PASSWORD=ragpass\
-e POSTGRES_DB=ragdb\
ankane/pgvector

Enable extension:

CREATE EXTENSION IF NOT EXISTS vector;

------------------------------------------------------------------------

## 2. Docker Redis (Celery Broker)

docker run -d -p 6379:6379 --name rag-redis redis

------------------------------------------------------------------------

## 3. Alembic Migration

alembic upgrade head

------------------------------------------------------------------------

# ▶ Running Project

docker start rag-postgres docker start rag-redis
venv`\Scripts`{=tex}`\activate`{=tex} celery -A
app.core.celery_app:celery worker --pool=solo -Q rag-queue
--loglevel=info uvicorn app.main:app --reload

Swagger:

http://127.0.0.1:8000/docs

------------------------------------------------------------------------

# 🧠 AI Enhancements Implemented

  Feature              Benefit
  -------------------- ---------------------------
  Vector Search        Semantic retrieval
  Synthetic FAQs       Retrieval boosting
  Memory               Conversational continuity
  Async Workers        Production reliability
  Grounded LLM         Prevent hallucinations
  Citations            Trust & explainability
  Confidence Scoring   Reliability indicator

------------------------------------------------------------------------

# 🏆 Enterprise Value

This project mirrors how companies build:

-   Internal AI assistants
-   Customer support bots
-   Private enterprise search
-   Knowledge retrieval platforms

Perfect for: ✔ Portfolio ✔ Freelancing ✔ Backend/AI Interviews

------------------------------------------------------------------------

# 👨‍💻 Author

Hritik Garg 🚀

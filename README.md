# 📚 Enterprise Business Knowledge Base Chatbot (RAG)

A production‑style Retrieval Augmented Generation (RAG) system that
allows organizations to upload internal documents (PDFs) and interact
with them through an AI chatbot powered by semantic search and a local
Large Language Model (LLM).

This project simulates how modern enterprise AI assistants (used in
SaaS, support portals, internal knowledge tools) are built --- combining
document processing, embeddings, vector databases, and grounded LLM
responses.

------------------------------------------------------------------------

# 🚀 Core Capabilities

-   Multi‑tenant architecture (organization‑isolated data)
-   JWT Authentication + secure user access
-   Organization‑scoped document uploads
-   PDF parsing → cleaning → chunking
-   Vector embeddings using Sentence Transformers
-   pgvector-powered similarity search
-   AI‑generated FAQs from uploaded documents
-   Conversational memory (recent chat context)
-   Local LLM answering via Ollama (offline)
-   Source citations in responses
-   Confidence scoring for answers

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
     │Postgres DB   │   │pgvector Index │    │Ollama LLM      │
     │(users/docs)  │   │(embeddings)   │    │(llama3:8b)     │
     └──────────────┘   └───────────────┘    └────────────────┘
                                ▲
                                │
                       ┌───────────────────┐
                       │ Embedding Model   │
                       │ MiniLM (HF)       │
                       └───────────────────┘

------------------------------------------------------------------------

# 🏗 Detailed Flow

## Document Upload Pipeline

1.  User uploads PDF under their organization
2.  File saved to org‑specific folder
3.  Text extracted using PyPDF
4.  Text normalized & cleaned
5.  Document split into overlapping chunks
6.  Each chunk embedded → stored in pgvector
7.  LLM generates synthetic FAQs from chunks
8.  FAQs also embedded & stored for better retrieval

------------------------------------------------------------------------

## Chat Pipeline

1.  User asks a question
2.  Question embedded
3.  Similarity search run within org scope
4.  Retrieve top matching chunks + synthetic FAQs
5.  Fetch last few chat messages for context
6.  Combine memory + KB context
7.  Send to Ollama LLM
8.  LLM generates grounded answer
9.  System returns:
    -   Answer
    -   Sources
    -   Confidence

------------------------------------------------------------------------

# 🐘 Database Usage

  Table                 Purpose
  --------------------- -----------------------------------
  users                 Org users & roles
  organizations         Multi‑tenant separation
  documents             Uploaded files metadata
  document_embeddings   Vectorized searchable knowledge
  chat_history          Stores recent conversation memory

------------------------------------------------------------------------

# 🔍 Why pgvector Instead of Pinecone?

-   Fully local & free
-   Runs inside Postgres
-   Production‑ready for SaaS apps
-   No external dependency

------------------------------------------------------------------------

# 🤖 Ollama Usage

-   Local LLM inference
-   No API costs
-   Enterprise privacy
-   Offline RAG chatbot simulation

------------------------------------------------------------------------

# ⚙ Setup Requirements

## 1. Docker Postgres with pgvector

``` bash
docker run -d \
  --name rag-postgres \
  -p 5432:5432 \
  -e POSTGRES_USER=raguser \
  -e POSTGRES_PASSWORD=ragpass \
  -e POSTGRES_DB=ragdb \
  ankane/pgvector
```

Enable extension:

``` sql
CREATE EXTENSION IF NOT EXISTS vector;
```

------------------------------------------------------------------------

## 2. Install Ollama

Download → https://ollama.com

Pull model:

``` bash
ollama pull llama3:8b
```

------------------------------------------------------------------------

# ▶ Running Project

``` bash
docker start rag-postgres
venv\Scripts\activate
uvicorn app.main:app --reload
```

Swagger:

    http://127.0.0.1:8000/docs

------------------------------------------------------------------------

# 🧠 AI Enhancements Implemented

  Feature              Benefit
  -------------------- ------------------------
  Vector Search        Semantic retrieval
  Synthetic FAQs       Better query matching
  Memory               Conversational context
  Grounded LLM         No hallucination
  Citations            Trust & explainability
  Confidence Scoring   Reliability indicator

------------------------------------------------------------------------

# 🏆 Enterprise Value

This project mirrors how companies build:

-   Internal AI assistants
-   Customer support bots
-   Private document chat systems
-   Knowledge retrieval tools

Perfect for: ✔ Portfolio\
✔ AI/Backend Freelancing\
✔ Interviews

------------------------------------------------------------------------

# 👨‍💻 Author

Hritik Garg

"""Process-wide singletons for expensive-to-build dependencies.

Building these per request is what made /chat slow: constructing
SentenceTransformerEmbeddingService loads MiniLM from disk (~4s),
and rebuilding the LLM client discards its HTTP connection pool.

lru_cache gives one instance per process — the API process and the
Celery worker process each get their own copy, built on first use.
The FastAPI lifespan calls these at startup so the first request
doesn't pay the model-load cost either.
"""
from functools import lru_cache

from app.domain.llm_service import LLMService
from app.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingService,
)
from app.infrastructure.llm.factory import build_llm_service


@lru_cache(maxsize=1)
def get_embedding_service() -> SentenceTransformerEmbeddingService:
    return SentenceTransformerEmbeddingService()


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return build_llm_service()

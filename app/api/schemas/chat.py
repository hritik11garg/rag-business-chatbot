from pydantic import BaseModel, Field

from app.core.config import settings


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Bounded so a client can't request the whole knowledge base as
    # context (prompt cost and quality both degrade with huge top_k).
    # Default and ceiling are the single source of truth in settings.
    top_k: int = Field(default=settings.DEFAULT_TOP_K, ge=1, le=settings.MAX_TOP_K)
    # Optional retrieval filter. Either omit it (search all documents)
    # or name at least one document — an empty list is rejected rather
    # than silently meaning "search nothing".
    document_ids: list[int] | None = Field(default=None, min_length=1)


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]
    confidence: str  # "high" | "medium" | "low"

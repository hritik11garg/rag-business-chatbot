from typing import List

from sentence_transformers import CrossEncoder

from app.core.config import settings


class CrossEncoderReranker:
    """Reranker backed by a sentence-transformers CrossEncoder.

    The model loads once (it's a few hundred MB) — construct it as a
    process-wide singleton, like the embedding model, not per request.
    """

    def __init__(self, model_name: str | None = None):
        self.model = CrossEncoder(model_name or settings.RERANK_MODEL)

    def rerank(self, *, query: str, passages: List[str]) -> List[int]:
        if not passages:
            return []
        # One forward pass per (query, passage) pair; higher score = more
        # relevant. Argsort descending gives the new ordering as indices.
        scores = self.model.predict([(query, p) for p in passages])
        return sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)

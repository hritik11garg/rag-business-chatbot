from typing import List
from sentence_transformers import SentenceTransformer

from app.domain.embedding_service import EmbeddingService


class SentenceTransformerEmbeddingService:
    """
    SentenceTransformer-based embedding implementation.
    """

    def __init__(self):
        # Load model ONCE
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return (
            self.model
            .encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            .tolist()
        )

    def embed_query(self, text: str) -> List[float]:
        return (
            self.model
            .encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            .tolist()
        )

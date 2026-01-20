from typing import List, Protocol


class EmbeddingService(Protocol):
    """
    Abstraction for embedding generation.
    """

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...

    def embed_query(self, text: str) -> List[float]:
        ...

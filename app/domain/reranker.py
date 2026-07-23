from typing import List, Protocol


class Reranker(Protocol):
    """Reorders retrieved passages by query relevance.

    A cross-encoder scores the (query, passage) pair jointly, which is more
    discriminating than the bi-encoder cosine distance used for the initial
    dense retrieval — at a cost that only makes sense on a small candidate
    pool, not the whole corpus. Hence the retrieve-wide-then-rerank shape.
    """

    def rerank(self, *, query: str, passages: List[str]) -> List[int]:
        """Return passage indices ordered most- to least-relevant.

        Indices reference the input `passages` list, so the caller reorders
        its own richer objects (rows, chunks) without this port needing to
        know their shape.
        """
        ...

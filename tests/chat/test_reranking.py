"""Reranking integration into the retrieval path.

The cross-encoder model isn't loaded here — a fake Reranker returns a known
ordering, so we test the WIRING: that a wider pool is fetched, reordered,
and cut to top_k. (The model's real quality is measured separately in
evals/retrieval_eval.py.)
"""

from app.core.config import settings
from app.db.models.user import User
from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase


class Row:
    def __init__(self, content, filename):
        self.content = content
        self.filename = filename


class FakeEmbeddingService:
    def embed_query(self, text):
        return [0.0, 0.0, 0.0]


class ReverseReranker:
    """Deterministic stand-in: reverses the pool order, so the test can
    assert the use case actually applied the reranker's ordering."""

    def rerank(self, *, query, passages):
        return list(range(len(passages)))[::-1]


def _use_case(monkeypatch, pool, reranker, use_hybrid=False, lexical=None):
    # similarity_search / lexical_search are module-level functions; patch
    # them to return controlled pools and record the LIMIT asked for.
    calls = {}

    def fake_search(*, db, organization_id, query_embedding, limit, document_ids=None):
        calls["dense_limit"] = limit
        return pool

    def fake_lexical(*, db, organization_id, query_text, limit, document_ids=None):
        calls["lexical_limit"] = limit
        return lexical or []

    monkeypatch.setattr("app.use_cases.chat_with_kb.similarity_search", fake_search)
    monkeypatch.setattr("app.use_cases.chat_with_kb.lexical_search", fake_lexical)
    uc = ChatWithKnowledgeBaseUseCase(
        embedding_service=FakeEmbeddingService(),
        llm_service=object(),
        chat_history=object(),
        db=None,
        reranker=reranker,
        use_hybrid=use_hybrid,
    )
    return uc, calls


def test_no_reranker_retrieves_exactly_top_k(monkeypatch):
    pool = [Row(f"c{i}", f"{i}.pdf") for i in range(5)]
    uc, calls = _use_case(monkeypatch, pool, reranker=None)
    user = User(id=1, email="e", hashed_password="x", organization_id=1)

    result = uc._retrieve(question="q", user=user, top_k=5, document_ids=None)

    assert calls["dense_limit"] == 5  # dense path asks for exactly top_k
    assert "lexical_limit" not in calls  # keyword arm not touched
    assert [r.filename for r in result] == ["0.pdf", "1.pdf", "2.pdf", "3.pdf", "4.pdf"]


def test_reranker_widens_pool_and_reorders_then_cuts(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_CANDIDATES", 20)
    pool = [Row(f"c{i}", f"{i}.pdf") for i in range(20)]
    uc, calls = _use_case(monkeypatch, pool, reranker=ReverseReranker())
    user = User(id=1, email="e", hashed_password="x", organization_id=1)

    result = uc._retrieve(question="q", user=user, top_k=3, document_ids=None)

    assert calls["dense_limit"] == 20  # wider candidate pool fetched
    # ReverseReranker puts index 19 first; top_k=3 keeps 19,18,17.
    assert [r.filename for r in result] == ["19.pdf", "18.pdf", "17.pdf"]


def test_reranker_handles_empty_pool(monkeypatch):
    uc, _ = _use_case(monkeypatch, pool=[], reranker=ReverseReranker())
    user = User(id=1, email="e", hashed_password="x", organization_id=1)
    assert uc._retrieve(question="q", user=user, top_k=5, document_ids=None) == []


class IdRow:
    """Row with an id (for RRF fusion) plus filename/content."""

    def __init__(self, cid, filename):
        self.id = cid
        self.filename = filename
        self.content = f"content-{cid}"


def test_hybrid_fuses_dense_and_lexical(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_CANDIDATES", 20)
    # A doc the keyword arm ranks #1 that dense missed entirely — RRF
    # should surface it into the fused top_k.
    dense = [IdRow(1, "a.pdf"), IdRow(2, "b.pdf")]
    lexical = [IdRow(9, "keyword-hit.pdf"), IdRow(1, "a.pdf")]
    uc, calls = _use_case(
        monkeypatch, pool=dense, reranker=None, use_hybrid=True, lexical=lexical
    )
    user = User(id=1, email="e", hashed_password="x", organization_id=1)

    result = uc._retrieve(question="krona", user=user, top_k=3, document_ids=None)

    assert calls["dense_limit"] == 20 and calls["lexical_limit"] == 20
    files = {r.filename for r in result}
    # doc 1 (in both arms) and the lexical-only doc 9 both present
    assert "a.pdf" in files and "keyword-hit.pdf" in files


def test_hybrid_composes_with_rerank(monkeypatch):
    monkeypatch.setattr(settings, "RERANK_CANDIDATES", 20)
    dense = [IdRow(1, "a.pdf"), IdRow(2, "b.pdf")]
    lexical = [IdRow(9, "c.pdf")]
    uc, _ = _use_case(
        monkeypatch,
        pool=dense,
        reranker=ReverseReranker(),
        use_hybrid=True,
        lexical=lexical,
    )
    user = User(id=1, email="e", hashed_password="x", organization_id=1)

    # Fused pool then reversed by the reranker, cut to top_k=2.
    result = uc._retrieve(question="q", user=user, top_k=2, document_ids=None)
    assert len(result) == 2


def test_cross_encoder_orders_by_descending_score(monkeypatch):
    # Unit-test the adapter's ordering logic without loading a real model.
    from app.infrastructure.rerank.cross_encoder import CrossEncoderReranker

    svc = CrossEncoderReranker.__new__(CrossEncoderReranker)

    class FakeModel:
        def predict(self, pairs):
            # score = length of the passage; longest should rank first
            return [len(p) for _, p in pairs]

    svc.model = FakeModel()
    order = svc.rerank(query="q", passages=["aa", "a", "aaaa", "aaa"])
    assert order == [2, 3, 0, 1]  # indices of "aaaa","aaa","aa","a"
    assert svc.rerank(query="q", passages=[]) == []

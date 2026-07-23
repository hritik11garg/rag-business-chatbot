"""Unit tests for the hybrid-retrieval building blocks: the RRF fusion
math and the injection-safe tsquery construction in lexical_search."""

from types import SimpleNamespace

from app.services.embedding_service import lexical_search, reciprocal_rank_fusion


def row(cid):
    return SimpleNamespace(id=cid, content=f"c{cid}", filename=f"{cid}.pdf")


def test_rrf_ranks_a_doc_found_by_both_arms_first():
    # Doc 1 is #2 in dense and #1 in lexical; doc 2 only in dense; doc 3
    # only in lexical. Appearing in both should win.
    dense = [row(2), row(1)]
    lexical = [row(1), row(3)]
    fused = reciprocal_rank_fusion(dense, lexical, limit=3)
    assert fused[0].id == 1  # in both lists -> highest fused score
    assert {r.id for r in fused} == {1, 2, 3}  # union, de-duplicated


def test_rrf_respects_limit_and_dedupes():
    dense = [row(1), row(2), row(3)]
    lexical = [row(1), row(2)]
    fused = reciprocal_rank_fusion(dense, lexical, limit=2)
    assert len(fused) == 2
    assert fused[0].id in (1, 2)


class _CaptureDB:
    """Records the bound parameters passed to db.execute."""

    def __init__(self):
        self.params = None

    def execute(self, sql, params):
        self.params = params

        class _Result:
            def fetchall(self_inner):
                return []

        return _Result()


def test_lexical_search_builds_or_tsquery_from_alnum_terms():
    db = _CaptureDB()
    lexical_search(db, organization_id=1, query_text="birth year of Devon Levi")
    # Stopword-ish words are kept as lemmas; OR-joined for recall.
    assert db.params["ts_query"] == "birth | year | of | devon | levi"


def test_lexical_search_strips_tsquery_operators_no_injection():
    db = _CaptureDB()
    # Hostile input full of tsquery metacharacters must be reduced to plain
    # OR-joined alphanumeric tokens — no operator can survive.
    lexical_search(db, organization_id=1, query_text="a & b ! (c:*) | d';drop")
    assert db.params["ts_query"] == "a | b | c | d | drop"


def test_lexical_search_empty_query_returns_empty_without_db():
    # No alphanumeric terms -> no query issued at all.
    class Boom:
        def execute(self, *a, **k):
            raise AssertionError("must not query on an empty tsquery")

    assert lexical_search(Boom(), organization_id=1, query_text="!!! ??? ...") == []

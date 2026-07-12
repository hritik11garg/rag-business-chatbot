"""Tenant isolation invariant of similarity_search.

The SQL sent to the database must filter on organization_id
UNCONDITIONALLY — with or without a document_ids narrowing filter.
These tests capture the statement a fake session receives; if someone
ever makes the org filter conditional, they fail.
"""

from app.services.embedding_service import similarity_search


class FakeResult:
    def fetchall(self):
        return []


class CapturingDB:
    def __init__(self):
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = str(sql)
        self.params = params
        return FakeResult()


QUERY_EMBEDDING = [0.1, 0.2, 0.3]


def test_org_filter_is_always_present():
    db = CapturingDB()
    similarity_search(db, organization_id=7, query_embedding=QUERY_EMBEDDING, limit=5)
    assert "de.organization_id = :org_id" in db.sql
    assert db.params["org_id"] == 7


def test_document_filter_narrows_within_the_org_filter():
    db = CapturingDB()
    similarity_search(
        db,
        organization_id=7,
        query_embedding=QUERY_EMBEDDING,
        limit=5,
        document_ids=[3, 4],
    )
    # BOTH filters present: document_ids narrows, never replaces
    assert "de.organization_id = :org_id" in db.sql
    assert "de.document_id IN" in db.sql
    assert db.params["org_id"] == 7
    assert db.params["doc_ids"] == [3, 4]


def test_no_document_filter_without_document_ids():
    db = CapturingDB()
    similarity_search(db, organization_id=7, query_embedding=QUERY_EMBEDDING, limit=5)
    assert "document_id IN" not in db.sql


def test_limit_is_parameterized():
    db = CapturingDB()
    similarity_search(db, organization_id=7, query_embedding=QUERY_EMBEDDING, limit=3)
    assert db.params["limit"] == 3

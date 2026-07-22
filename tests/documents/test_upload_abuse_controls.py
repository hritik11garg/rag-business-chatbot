"""Abuse controls on the ingestion pipeline (OWASP A04/A05).

Rate limiting bounds how fast a tenant can upload; these bound the damage
of the uploads that get through: total corpus size per org, and how many
LLM calls one upload can amplify into via FAQ generation.
"""

import io

import pytest
from fastapi import UploadFile

from app.core.config import settings
from app.use_cases import upload_document as upload_module
from app.use_cases.upload_document import (
    DocumentQuotaExceededError,
    UploadDocumentUseCase,
)
from app.db.models.user import User

USER = User(id=1, email="a@b.c", hashed_password="x", organization_id=7, is_active=True)


class FakeQuery:
    def __init__(self, count):
        self._count = count

    def filter(self, *a, **k):
        return self

    def count(self):
        return self._count


class FakeDB:
    """Reports a fixed document count; explodes if anything tries to write,
    proving the quota check short-circuits before any I/O."""

    def __init__(self, doc_count):
        self.doc_count = doc_count

    def query(self, *a, **k):
        return FakeQuery(self.doc_count)

    def add(self, *a, **k):
        raise AssertionError("must not write once the quota is exceeded")


def make_upload() -> UploadFile:
    return UploadFile(filename="x.pdf", file=io.BytesIO(b"%PDF-1.4 data"))


def test_upload_rejected_when_org_at_quota(monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCUMENTS_PER_ORG", 3)
    use_case = UploadDocumentUseCase(FakeDB(3), embedding_service=object())

    upload = make_upload()
    upload.file.seek(0)
    # content_type must pass the earlier check to reach the quota gate
    monkeypatch.setattr(type(upload), "content_type", "application/pdf", raising=False)

    with pytest.raises(DocumentQuotaExceededError):
        use_case.execute(file=upload, user=USER)


def test_faq_generation_is_capped_to_max_chunks(monkeypatch):
    """One LLM call per chunk means an uncapped chunk list turns a single
    upload into hundreds of paid calls — the cap is the amplification bound."""
    monkeypatch.setattr(settings, "MAX_FAQ_CHUNKS", 4)

    chunks = [f"chunk-{i}" for i in range(50)]
    scheduled = {}

    monkeypatch.setattr(upload_module, "extract_text_from_pdf", lambda p: "raw")
    monkeypatch.setattr(upload_module, "normalize_text", lambda t: t)
    monkeypatch.setattr(upload_module, "chunk_text", lambda t: chunks)
    monkeypatch.setattr(upload_module, "store_embeddings", lambda **kw: None)
    monkeypatch.setattr(upload_module.os, "remove", lambda p: None)

    class Doc:
        id = 11
        filename = "x.pdf"

    class DB:
        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            pass

    use_case = UploadDocumentUseCase(
        DB(),
        embedding_service=object(),
        schedule_faq_generation=lambda c, d, o: scheduled.update(chunks=c),
    )
    monkeypatch.setattr(upload_module, "Document", lambda **kw: Doc())

    use_case.ingest_pdf(file_path="x.pdf", organization_id=7, uploaded_by=1)

    assert len(scheduled["chunks"]) == 4  # not 50
    assert scheduled["chunks"] == chunks[:4]

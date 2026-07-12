"""Upload/ingest pipeline: domain exceptions, cleanup, FAQ injection.

Pure unit tests — the PDF text pipeline and embedding store are
monkeypatched, the DB session is a fake. What's under test is the use
case's contract: failures delete the file (and the row, if created),
success reports chunks and fires the injected scheduler exactly once.
"""

import pytest

import app.use_cases.upload_document as upload_module
from app.use_cases.upload_document import (
    EmbeddingStorageError,
    UnreadablePdfError,
    UploadDocumentUseCase,
)


class FakeSession:
    def __init__(self):
        self.added = []
        self.deleted = []

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        obj.id = 42


class FakeEmbeddingService:
    def embed_texts(self, texts):
        return [[0.0] * 3 for _ in texts]


def make_pdf(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-fake")
    return pdf


def patch_pipeline(monkeypatch, chunks):
    monkeypatch.setattr(upload_module, "extract_text_from_pdf", lambda path: "raw")
    monkeypatch.setattr(upload_module, "normalize_text", lambda text: "clean")
    monkeypatch.setattr(upload_module, "chunk_text", lambda text: chunks)


def test_unreadable_pdf_raises_and_removes_file(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path)
    monkeypatch.setattr(
        upload_module,
        "extract_text_from_pdf",
        lambda path: (_ for _ in ()).throw(ValueError("bad pdf")),
    )
    use_case = UploadDocumentUseCase(
        FakeSession(), embedding_service=FakeEmbeddingService()
    )

    with pytest.raises(UnreadablePdfError):
        use_case.ingest_pdf(file_path=str(pdf), organization_id=1, uploaded_by=1)
    assert not pdf.exists()


def test_empty_pdf_raises_and_removes_file(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path)
    patch_pipeline(monkeypatch, chunks=[])
    use_case = UploadDocumentUseCase(
        FakeSession(), embedding_service=FakeEmbeddingService()
    )

    with pytest.raises(UnreadablePdfError):
        use_case.ingest_pdf(file_path=str(pdf), organization_id=1, uploaded_by=1)
    assert not pdf.exists()


def test_embedding_failure_rolls_back_row_and_file(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path)
    patch_pipeline(monkeypatch, chunks=["c1", "c2"])

    def broken_store(**kwargs):
        raise RuntimeError("pgvector down")

    monkeypatch.setattr(upload_module, "store_embeddings", broken_store)
    db = FakeSession()
    use_case = UploadDocumentUseCase(db, embedding_service=FakeEmbeddingService())

    with pytest.raises(EmbeddingStorageError):
        use_case.ingest_pdf(file_path=str(pdf), organization_id=1, uploaded_by=1)
    assert not pdf.exists()  # no orphaned file
    assert db.deleted == db.added  # the Document row did not survive


def test_success_fires_injected_scheduler(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path)
    patch_pipeline(monkeypatch, chunks=["c1", "c2", "c3"])
    monkeypatch.setattr(upload_module, "store_embeddings", lambda **kwargs: None)

    calls = []
    use_case = UploadDocumentUseCase(
        FakeSession(),
        embedding_service=FakeEmbeddingService(),
        schedule_faq_generation=lambda chunks, doc_id, org_id: calls.append(
            (chunks, doc_id, org_id)
        ),
    )

    result = use_case.ingest_pdf(file_path=str(pdf), organization_id=7, uploaded_by=1)

    assert result["chunks_stored"] == 3
    assert result["id"] == 42
    assert calls == [(["c1", "c2", "c3"], 42, 7)]
    assert pdf.exists()


def test_bulk_mode_none_scheduler_schedules_nothing(tmp_path, monkeypatch):
    pdf = make_pdf(tmp_path)
    patch_pipeline(monkeypatch, chunks=["c1"])
    monkeypatch.setattr(upload_module, "store_embeddings", lambda **kwargs: None)

    use_case = UploadDocumentUseCase(
        FakeSession(),
        embedding_service=FakeEmbeddingService(),
        schedule_faq_generation=None,
    )
    result = use_case.ingest_pdf(file_path=str(pdf), organization_id=1, uploaded_by=1)
    assert result["chunks_stored"] == 1  # and no AttributeError from a None call

"""Delete: domain exception, commit-before-file-removal ordering,
missing-file tolerance. The fake session deliberately has NO execute()
method — if the use case ever regresses to raw-SQL embedding deletes,
these tests crash with AttributeError."""

import pytest

import app.use_cases.delete_document as delete_module
from app.db.models.document import Document
from app.db.models.user import User
from app.use_cases.delete_document import (
    DeleteDocumentUseCase,
    DocumentNotFoundError,
)


def make_user():
    return User(id=1, email="u@x.com", hashed_password="x", organization_id=7)


class FakeQuery:
    def __init__(self, document):
        self.document = document

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.document


class FakeSession:
    def __init__(self, document, events):
        self.document = document
        self.events = events

    def query(self, model):
        return FakeQuery(self.document)

    def delete(self, obj):
        self.events.append("db-delete")

    def commit(self):
        self.events.append("commit")


def test_missing_document_raises_domain_error():
    db = FakeSession(document=None, events=[])
    with pytest.raises(DocumentNotFoundError):
        DeleteDocumentUseCase(db).execute(document_id=99, user=make_user())


def test_commit_happens_before_file_removal(monkeypatch):
    events = []
    doc = Document(
        id=5,
        filename="a.pdf",
        content_type="application/pdf",
        organization_id=7,
        uploaded_by=1,
    )
    monkeypatch.setattr(delete_module.os.path, "exists", lambda p: True)
    monkeypatch.setattr(
        delete_module.os, "remove", lambda p: events.append("file-remove")
    )

    result = DeleteDocumentUseCase(FakeSession(doc, events)).execute(
        document_id=5, user=make_user()
    )

    # DB state is settled before the file goes — a failed commit must
    # never leave a row whose file is already gone.
    assert events == ["db-delete", "commit", "file-remove"]
    assert "message" in result


def test_missing_file_on_disk_is_tolerated(monkeypatch):
    events = []
    doc = Document(
        id=5,
        filename="a.pdf",
        content_type="application/pdf",
        organization_id=7,
        uploaded_by=1,
    )
    monkeypatch.setattr(delete_module.os.path, "exists", lambda p: False)

    result = DeleteDocumentUseCase(FakeSession(doc, events)).execute(
        document_id=5, user=make_user()
    )
    assert events == ["db-delete", "commit"]
    assert "message" in result

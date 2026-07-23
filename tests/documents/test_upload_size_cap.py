"""Upload size cap: the only pre-parser defense against a hostile
upload (content-type is a client-controlled header)."""

import io

import pytest

from app.core.config import settings
from app.db.models.user import User
from tests.documents.fakes import UnderQuotaDB
from app.use_cases.upload_document import (
    FileTooLargeError,
    InvalidContentTypeError,
    UploadDocumentUseCase,
)


class FakeUpload:
    """Duck-typed stand-in for fastapi.UploadFile (only the three
    attributes execute() touches)."""

    def __init__(self, data: bytes, filename="big.pdf"):
        self.file = io.BytesIO(data)
        self.filename = filename
        self.content_type = "application/pdf"


def make_user():
    return User(id=1, email="u@x.com", hashed_password="x", organization_id=3)


def test_oversized_upload_is_rejected_and_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # uploads/ dir is cwd-relative
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    # Valid PDF magic so we exercise the SIZE cap, not the magic check.
    upload = FakeUpload(b"%PDF-" + b"x" * (2 * 1024 * 1024))  # > 1 MB cap

    use_case = UploadDocumentUseCase(db=UnderQuotaDB(), embedding_service=None)
    with pytest.raises(FileTooLargeError):  # route maps this to 413
        use_case.execute(file=upload, user=make_user())

    org_dir = tmp_path / "uploads" / "org_3"
    assert list(org_dir.iterdir()) == []  # partial file cleaned up


def test_non_pdf_content_type_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    upload = FakeUpload(b"data", filename="x.exe")
    upload.content_type = "application/octet-stream"

    use_case = UploadDocumentUseCase(db=UnderQuotaDB(), embedding_service=None)
    with pytest.raises(InvalidContentTypeError):  # route maps this to 400
        use_case.execute(file=upload, user=make_user())

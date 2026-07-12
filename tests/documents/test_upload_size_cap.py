"""Upload size cap: the only pre-parser defense against a hostile
upload (content-type is a client-controlled header)."""

import io

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.db.models.user import User
from app.use_cases.upload_document import UploadDocumentUseCase


class FakeUpload:
    """Duck-typed stand-in for fastapi.UploadFile (only the three
    attributes execute() touches)."""

    def __init__(self, data: bytes, filename="big.pdf"):
        self.file = io.BytesIO(data)
        self.filename = filename
        self.content_type = "application/pdf"


def make_user():
    return User(id=1, email="u@x.com", hashed_password="x", organization_id=3)


def test_oversized_upload_is_413_and_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # uploads/ dir is cwd-relative
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    upload = FakeUpload(b"x" * (2 * 1024 * 1024))  # 2 MB > 1 MB cap

    use_case = UploadDocumentUseCase(db=None, embedding_service=None)
    with pytest.raises(HTTPException) as exc_info:
        use_case.execute(file=upload, user=make_user())

    assert exc_info.value.status_code == 413
    org_dir = tmp_path / "uploads" / "org_3"
    assert list(org_dir.iterdir()) == []  # partial file cleaned up


def test_non_pdf_content_type_is_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    upload = FakeUpload(b"data", filename="x.exe")
    upload.content_type = "application/octet-stream"

    use_case = UploadDocumentUseCase(db=None, embedding_service=None)
    with pytest.raises(HTTPException) as exc_info:
        use_case.execute(file=upload, user=make_user())
    assert exc_info.value.status_code == 400

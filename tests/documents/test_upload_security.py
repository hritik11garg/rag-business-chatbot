"""Upload security: filename sanitization (path traversal) and the
PDF magic-byte content check. These pin the fixes for the audit's
Critical arbitrary-write finding."""

import io
import os

import pytest

from app.db.models.user import User
from tests.documents.fakes import UnderQuotaDB
from app.use_cases.upload_document import (
    NotAPdfError,
    UploadDocumentUseCase,
    safe_pdf_filename,
)


class FakeUpload:
    def __init__(self, data: bytes, filename: str):
        self.file = io.BytesIO(data)
        self.filename = filename
        self.content_type = "application/pdf"


def make_user():
    return User(id=1, email="u@x.com", hashed_password="x", organization_id=3)


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../../etc/cron.d/evil",
        "..\\..\\..\\Windows\\System32\\evil",
        "/etc/passwd",
        "C:\\Windows\\Temp\\evil.exe",
        "....//....//evil",
        "normal/../../escape",
        "",
        None,
    ],
)
def test_safe_pdf_filename_never_contains_a_separator(hostile):
    result = safe_pdf_filename(hostile)
    assert "/" not in result
    assert "\\" not in result
    assert not result.startswith(".")
    assert result.endswith(".pdf")


def test_traversal_filename_writes_only_inside_org_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # A canary the attacker would try to overwrite one level up.
    canary = tmp_path / "canary.txt"
    canary.write_text("original")

    upload = FakeUpload(b"%PDF-1.4 fake", filename="../../canary.txt")
    use_case = UploadDocumentUseCase(db=UnderQuotaDB(), embedding_service=None)

    # ingest_pdf will fail parsing the fake PDF, but that's after the
    # write — what matters is WHERE it wrote. Patch ingest out.
    monkeypatch.setattr(
        use_case, "ingest_pdf", lambda **kw: {"ok": True, "path": kw["file_path"]}
    )
    result = use_case.execute(file=upload, user=make_user())

    assert canary.read_text() == "original"  # untouched
    assert os.path.dirname(result["path"]).endswith(os.path.join("uploads", "org_3"))


def test_non_pdf_magic_bytes_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Header claims PDF, bytes are an executable — must be rejected. The
    # use case raises a domain exception; the route maps it to 415.
    upload = FakeUpload(b"MZ\x90\x00 this is a PE binary", filename="x.pdf")
    use_case = UploadDocumentUseCase(db=UnderQuotaDB(), embedding_service=None)

    with pytest.raises(NotAPdfError):
        use_case.execute(file=upload, user=make_user())
    org_dir = tmp_path / "uploads" / "org_3"
    assert list(org_dir.iterdir()) == []  # nothing left on disk

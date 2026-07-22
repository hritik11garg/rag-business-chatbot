import os
import re
import uuid
from typing import Callable

from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.domain.embedding_service import EmbeddingService
from app.db.models.document import Document
from app.db.models.user import User
from app.services.document_processing import (
    extract_text_from_pdf,
    normalize_text,
    chunk_text,
)
from app.services.embedding_service import store_embeddings


UPLOAD_BASE_DIR = "uploads"

# PDF magic number — the first bytes of every valid PDF.
PDF_MAGIC = b"%PDF-"

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def safe_pdf_filename(raw: str | None) -> str:
    """Reduce a client-supplied filename to a safe, separator-free name.

    The upload filename is fully attacker-controlled. Feeding it to
    os.path.join is a path-traversal / arbitrary-write hole: '../../x',
    an absolute POSIX path, or a Windows 'C:\\...' path all escape the
    org directory. We keep only the final component (stripping BOTH
    separators, since os.path.basename ignores '\\' on POSIX), allow
    only [A-Za-z0-9._-], and force a .pdf extension. The result can
    never contain a separator, so it cannot traverse.
    """
    base = (raw or "").replace("\\", "/").split("/")[-1]
    name = os.path.splitext(base)[0]
    name = _UNSAFE_FILENAME_CHARS.sub("_", name).strip("._")
    return f"{name or uuid.uuid4().hex}.pdf"


class DocumentQuotaExceededError(Exception):
    """The organization already holds MAX_DOCUMENTS_PER_ORG documents.

    Rate limiting bounds how FAST a tenant can upload; this bounds how
    MUCH they can accumulate, so one org can't exhaust shared storage.
    """


class PdfIngestError(Exception):
    """The saved PDF could not be ingested; the file has been removed."""


class UnreadablePdfError(PdfIngestError):
    """Corrupted, image-only, or empty PDF."""


class EmbeddingStorageError(PdfIngestError):
    """Chunks extracted but embedding generation or storage failed."""


class UploadDocumentUseCase:
    """
    Handles document upload + ingestion into the RAG system.

    schedule_faq_generation is injected so the caller decides whether FAQ
    generation happens: the API route wires the Celery task, while bulk
    ingestion passes None (500 docs must not enqueue 500 LLM jobs).
    """

    def __init__(
        self,
        db: Session,
        *,
        embedding_service: EmbeddingService,
        schedule_faq_generation: Callable[[list[str], int, int], None] | None = None,
    ):
        self.db = db
        self.embedding_service = embedding_service
        self.schedule_faq_generation = schedule_faq_generation

    def execute(self, *, file: UploadFile, user: User) -> dict:
        """HTTP-facing path: validate, save the upload, then ingest."""
        if file.content_type != "application/pdf":
            raise HTTPException(400, "Only PDF files are supported")

        # Per-tenant corpus cap, checked before a single byte is written.
        existing = (
            self.db.query(Document)
            .filter(Document.organization_id == user.organization_id)
            .count()
        )
        if existing >= settings.MAX_DOCUMENTS_PER_ORG:
            raise DocumentQuotaExceededError(
                f"Organization document limit of "
                f"{settings.MAX_DOCUMENTS_PER_ORG} reached"
            )

        # Org isolation folder
        org_dir = os.path.join(UPLOAD_BASE_DIR, f"org_{user.organization_id}")
        os.makedirs(org_dir, exist_ok=True)

        # Sanitize the attacker-controlled filename BEFORE it touches the
        # filesystem — this is the traversal / arbitrary-write defense.
        safe_name = safe_pdf_filename(file.filename)
        name, ext = os.path.splitext(safe_name)
        file_path = os.path.join(org_dir, safe_name)
        counter = 1

        while os.path.exists(file_path):
            counter += 1
            file_path = os.path.join(org_dir, f"{name}_v{counter}{ext}")

        # Stream to disk with a size cap and a content-signature check.
        # The content-type header is client-controlled, so neither it nor
        # the filename is trusted: we verify the PDF magic bytes and cap
        # the size, both before the parser runs.
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        file.file.seek(0)
        written = 0
        too_large = False
        not_pdf = False
        first_block = True
        with open(file_path, "wb") as f:
            while block := file.file.read(1024 * 1024):
                if first_block:
                    first_block = False
                    if not block.startswith(PDF_MAGIC):
                        not_pdf = True
                        break
                written += len(block)
                if written > max_bytes:
                    too_large = True
                    break
                f.write(block)
        if not_pdf:
            os.remove(file_path)
            raise HTTPException(415, "File content is not a valid PDF")
        if too_large:
            os.remove(file_path)
            raise HTTPException(
                413, f"File exceeds the {settings.MAX_UPLOAD_MB} MB upload limit"
            )

        try:
            return self.ingest_pdf(
                file_path=file_path,
                organization_id=user.organization_id,
                uploaded_by=user.id,
            )
        except UnreadablePdfError as exc:
            raise HTTPException(400, str(exc)) from exc
        except EmbeddingStorageError as exc:
            raise HTTPException(500, str(exc)) from exc

    def ingest_pdf(
        self, *, file_path: str, organization_id: int, uploaded_by: int
    ) -> dict:
        """Core ingestion for an already-saved PDF — no HTTP types.

        Deletes the file on failure so callers never accumulate PDFs that
        can't be served as sources.
        """
        try:
            raw_text = extract_text_from_pdf(file_path)
            clean_text = normalize_text(raw_text)
            chunks = chunk_text(clean_text)
        except Exception as exc:
            os.remove(file_path)
            raise UnreadablePdfError("Corrupted or unreadable PDF") from exc

        if not chunks:
            os.remove(file_path)
            raise UnreadablePdfError("No readable content found")

        # Store document metadata
        document = Document(
            filename=os.path.basename(file_path),
            content_type="application/pdf",
            organization_id=organization_id,
            uploaded_by=uploaded_by,
        )

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        try:
            store_embeddings(
                db=self.db,
                organization_id=organization_id,
                document=document,
                chunks=chunks,
                embedding_service=self.embedding_service,
            )
        except Exception as exc:
            self.db.delete(document)
            self.db.commit()
            os.remove(file_path)
            raise EmbeddingStorageError("Embedding generation failed") from exc

        if self.schedule_faq_generation is not None:
            # FAQ generation costs ONE LLM call per chunk, so an unbounded
            # chunk list turns a single upload into hundreds of paid calls.
            # Cap it: the first N chunks are the most representative anyway.
            self.schedule_faq_generation(
                chunks[: settings.MAX_FAQ_CHUNKS], document.id, organization_id
            )

        return {
            "id": document.id,
            "filename": document.filename,
            "organization_id": organization_id,
            "chunks_stored": len(chunks),
        }

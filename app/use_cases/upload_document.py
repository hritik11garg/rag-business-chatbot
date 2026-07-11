import os
from typing import Callable

from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException

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

        # Org isolation folder
        org_dir = os.path.join(UPLOAD_BASE_DIR, f"org_{user.organization_id}")
        os.makedirs(org_dir, exist_ok=True)

        # Filename versioning
        name, ext = os.path.splitext(file.filename)
        file_path = os.path.join(org_dir, file.filename)
        counter = 1

        while os.path.exists(file_path):
            counter += 1
            file_path = os.path.join(org_dir, f"{name}_v{counter}{ext}")

        file.file.seek(0)

        with open(file_path, "wb") as f:
            f.write(file.file.read())

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
            self.schedule_faq_generation(chunks, document.id, organization_id)

        return {
            "id": document.id,
            "filename": document.filename,
            "organization_id": organization_id,
            "chunks_stored": len(chunks),
        }

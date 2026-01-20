import os
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException

from app.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingService,
)
from app.db.models.document import Document
from app.db.models.user import User
from app.services.document_processing import (
    extract_text_from_pdf,
    normalize_text,
    chunk_text,
)
from app.services.embedding_service import store_embeddings
from app.tasks.faq_tasks import generate_faqs_task


UPLOAD_BASE_DIR = "uploads"


class UploadDocumentUseCase:
    """
    Handles document upload + ingestion into the RAG system.
    """

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = SentenceTransformerEmbeddingService()

    def execute(self, *, file: UploadFile, user: User) -> dict:
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

        final_filename = os.path.basename(file_path)
        file.file.seek(0)

        # Save file
        with open(file_path, "wb") as f:
            f.write(file.file.read())

        # Validate & extract text
        try:
            raw_text = extract_text_from_pdf(file_path)
            clean_text = normalize_text(raw_text)
            chunks = chunk_text(clean_text)
        except Exception:
            os.remove(file_path)
            raise HTTPException(400, "Corrupted or unreadable PDF")

        if not chunks:
            os.remove(file_path)
            raise HTTPException(400, "No readable content found")

        # Store document metadata
        document = Document(
            filename=final_filename,
            content_type=file.content_type,
            organization_id=user.organization_id,
            uploaded_by=user.id,
        )

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        # Store embeddings (SOLID-compliant)
        try:
            store_embeddings(
                db=self.db,
                organization_id=user.organization_id,
                document=document,
                chunks=chunks,
                embedding_service=self.embedding_service,
            )
        except Exception:
            self.db.delete(document)
            self.db.commit()
            os.remove(file_path)
            raise HTTPException(500, "Embedding generation failed")

        # Send FAQs to background worker
        generate_faqs_task.delay(chunks, document.id, user.organization_id)

        return {
            "id": document.id,
            "filename": document.filename,
            "organization_id": document.organization_id,
            "chunks_stored": len(chunks),
        }

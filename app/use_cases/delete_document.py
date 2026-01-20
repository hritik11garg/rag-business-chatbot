import os
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.db.models.document import Document
from app.db.models.user import User


UPLOAD_BASE_DIR = "uploads"


class DeleteDocumentUseCase:
    """
    Handles deletion of a document and its associated data.
    """

    def __init__(self, db: Session):
        self.db = db

    def execute(self, *, document_id: int, user: User) -> dict:
        document = (
            self.db.query(Document)
            .filter(
                Document.id == document_id,
                Document.organization_id == user.organization_id,
            )
            .first()
        )

        if not document:
            raise HTTPException(404, "Document not found")

        # Remove embeddings
        self.db.execute(
            text("DELETE FROM document_embeddings WHERE document_id = :doc_id"),
            {"doc_id": document_id},
        )

        # Remove file from disk
        file_path = os.path.join(
            UPLOAD_BASE_DIR,
            f"org_{user.organization_id}",
            document.filename,
        )

        if os.path.exists(file_path):
            os.remove(file_path)

        # Remove document record
        self.db.delete(document)
        self.db.commit()

        return {"message": "Document and embeddings deleted successfully"}

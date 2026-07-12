import logging
import os

from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.user import User

UPLOAD_BASE_DIR = "uploads"

logger = logging.getLogger(__name__)


class DocumentNotFoundError(Exception):
    """No such document in this organization; the route maps to 404."""


class DeleteDocumentUseCase:
    """
    Deletes a document row (embeddings go with it via the FK cascade,
    migration 7446a24eef9e) and then its file on disk.

    Ordering matters: the DB commit happens FIRST. If the commit fails,
    the file is still on disk and the state is fully consistent. A file
    that outlives its row is a cleanup nuisance; a row that outlives
    its file is a document that can be cited but never served.
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
            raise DocumentNotFoundError("Document not found")

        file_path = os.path.join(
            UPLOAD_BASE_DIR,
            f"org_{user.organization_id}",
            document.filename,
        )

        self.db.delete(document)  # embeddings cascade at the DB level
        self.db.commit()

        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            logger.warning(
                "deleted document had no file on disk",
                extra={"document_id": document_id, "path": file_path},
            )

        logger.info(
            "document deleted",
            extra={"document_id": document_id, "organization_id": user.organization_id},
        )
        return {"message": "Document and embeddings deleted successfully"}

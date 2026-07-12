from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.user import User


class ListDocumentsUseCase:
    """Org-scoped document listing — the org filter lives here, not in
    the route, so every caller gets tenant isolation for free."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, *, user: User) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(Document.organization_id == user.organization_id)
            .order_by(Document.id.desc())
            .all()
        )

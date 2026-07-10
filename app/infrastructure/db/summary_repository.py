from sqlalchemy.orm import Session

from app.db.models.conversation_summary import ConversationSummary


class DBConversationSummaryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self, *, user_id: int) -> str | None:
        row = (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.user_id == user_id)
            .first()
        )
        return row.summary if row else None

    def upsert_summary(
        self, *, user_id: int, organization_id: int, summary: str
    ) -> None:
        row = (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.user_id == user_id)
            .first()
        )
        if row:
            row.summary = summary
        else:
            self.db.add(
                ConversationSummary(
                    user_id=user_id,
                    organization_id=organization_id,
                    summary=summary,
                )
            )
        self.db.commit()

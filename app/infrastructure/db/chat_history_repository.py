from sqlalchemy.orm import Session
from typing import List

from app.db.models.chat_history import ChatHistory
from app.domain.chat_history_repository import ChatHistoryRepository

HISTORY_LIMIT = 6


class DBChatHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_recent_history(self, *, user_id: int) -> List[ChatHistory]:
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(HISTORY_LIMIT)
            .all()[::-1]
        )

    def save_message(
        self,
        *,
        user_id: int,
        organization_id: int,
        role: str,
        message: str,
    ) -> None:
        self.db.add(
            ChatHistory(
                user_id=user_id,
                organization_id=organization_id,
                role=role,
                message=message,
            )
        )
        self.db.commit()

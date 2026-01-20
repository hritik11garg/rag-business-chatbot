from sqlalchemy.orm import Session

from app.infrastructure.db.chat_history_repository import DBChatHistoryRepository


def get_recent_history(db: Session, *, user_id: int):
    return DBChatHistoryRepository(db).get_recent_history(user_id=user_id)


def save_message(
    db: Session,
    *,
    user_id: int,
    organization_id: int,
    role: str,
    message: str,
):
    DBChatHistoryRepository(db).save_message(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        message=message,
    )

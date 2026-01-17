from sqlalchemy.orm import Session
from app.db.models.chat_history import ChatHistory


HISTORY_LIMIT = 6  # last 6 messages only


def get_recent_history(db: Session, *, user_id: int):
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(HISTORY_LIMIT)
        .all()[::-1]
    )


def save_message(db: Session, *, user_id: int, organization_id: int, role: str, message: str):
    db.add(
        ChatHistory(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            message=message,
        )
    )
    db.commit()

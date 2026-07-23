from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey

from app.db.base import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    # ON DELETE CASCADE: chat turns hold the user's questions and the AI's
    # answers over org documents — business-sensitive content. Deleting the
    # user or org must erase it, so the schema (not application code) owns
    # that cleanup rule as the single source of truth.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    role = Column(Text)  # "user" or "assistant"
    message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Text, DateTime

from app.db.base import Base


class ConversationSummary(Base):
    """Rolling 'important facts' memory, one row per user.

    Updated off the critical path by a Celery task after each chat
    exchange; the chat prompt injects it as a small constant-size block
    so long conversations don't grow the prompt.
    """

    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    organization_id = Column(Integer, index=True, nullable=False)
    summary = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

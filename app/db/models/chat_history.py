from sqlalchemy import Column, Integer, Text, DateTime
from datetime import datetime, timezone
from app.db.base import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    organization_id = Column(Integer, index=True)
    role = Column(Text)  # "user" or "assistant"
    message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

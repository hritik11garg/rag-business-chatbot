from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    """
    Represents a company / client using the system.
    Each organization owns its users and documents.
    """

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Relationship: one organization → many users
    users = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

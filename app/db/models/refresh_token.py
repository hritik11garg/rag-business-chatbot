from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class RefreshToken(Base):
    """One row per issued refresh token (server-side rotation state).

    Access tokens stay stateless and short-lived; refresh tokens are
    tracked here so they can be rotated, revoked (logout), and — via the
    shared family_id lineage — invalidated wholesale when a already-used
    token is replayed (token-reuse / theft detection).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # The token's unique id (JWT `jti` claim). Looked up on every refresh.
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Rotation lineage: every token descended from one login shares this.
    family_id: Mapped[str] = mapped_column(String(64), index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

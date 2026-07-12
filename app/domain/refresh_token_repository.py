from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RefreshTokenRecord:
    """Read model for a stored refresh token — no ORM leakage across
    the port, so the token service stays trivially unit-testable."""

    jti: str
    family_id: str
    user_id: int
    revoked: bool
    expires_at: datetime


class RefreshTokenRepository(Protocol):
    def create(
        self, *, jti: str, family_id: str, user_id: int, expires_at: datetime
    ) -> None: ...

    def get(self, *, jti: str) -> RefreshTokenRecord | None: ...

    def revoke(self, *, jti: str) -> None: ...

    def revoke_family(self, *, family_id: str) -> None: ...

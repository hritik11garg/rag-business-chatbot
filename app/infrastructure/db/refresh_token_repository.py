from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models.refresh_token import RefreshToken
from app.domain.refresh_token_repository import RefreshTokenRecord


class DBRefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, jti: str, family_id: str, user_id: int, expires_at: datetime
    ) -> None:
        self.db.add(
            RefreshToken(
                jti=jti,
                family_id=family_id,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        self.db.commit()

    def get(self, *, jti: str) -> RefreshTokenRecord | None:
        row = self.db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
        if row is None:
            return None
        return RefreshTokenRecord(
            jti=row.jti,
            family_id=row.family_id,
            user_id=row.user_id,
            revoked=row.revoked,
            expires_at=row.expires_at,
        )

    def revoke(self, *, jti: str) -> None:
        self.db.query(RefreshToken).filter(RefreshToken.jti == jti).update(
            {"revoked": True}
        )
        self.db.commit()

    def revoke_family(self, *, family_id: str) -> None:
        self.db.query(RefreshToken).filter(RefreshToken.family_id == family_id).update(
            {"revoked": True}
        )
        self.db.commit()

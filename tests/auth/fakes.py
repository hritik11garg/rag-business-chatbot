"""Shared auth test doubles."""

from app.domain.refresh_token_repository import RefreshTokenRecord


class FakeRefreshTokenRepository:
    """In-memory RefreshTokenRepository — dict of jti -> record."""

    def __init__(self):
        self.records: dict[str, RefreshTokenRecord] = {}

    def create(self, *, jti, family_id, user_id, expires_at):
        self.records[jti] = RefreshTokenRecord(
            jti=jti,
            family_id=family_id,
            user_id=user_id,
            revoked=False,
            expires_at=expires_at,
        )

    def get(self, *, jti):
        return self.records.get(jti)

    def revoke(self, *, jti):
        rec = self.records.get(jti)
        if rec:
            self.records[jti] = RefreshTokenRecord(
                jti=rec.jti,
                family_id=rec.family_id,
                user_id=rec.user_id,
                revoked=True,
                expires_at=rec.expires_at,
            )

    def revoke_family(self, *, family_id):
        for jti, rec in list(self.records.items()):
            if rec.family_id == family_id:
                self.records[jti] = RefreshTokenRecord(
                    jti=rec.jti,
                    family_id=rec.family_id,
                    user_id=rec.user_id,
                    revoked=True,
                    expires_at=rec.expires_at,
                )

"""Refresh-token issuance, rotation, and revocation.

Business logic lives here, not in the route: the route only maps the
domain exceptions to 401s. Injected with a repository (a Protocol) and
a user loader, so it is fully unit-testable with fakes.

Security model:
- Access tokens are stateless and short-lived (not tracked here).
- Refresh tokens are single-use: each /refresh rotates to a new token
  and revokes the old one. If an ALREADY-revoked token is presented,
  that means either a replay or a stolen token racing the legitimate
  client — we revoke the entire family (every token descended from the
  original login), forcing re-authentication. This is refresh-token
  reuse detection (OWASP A07).
"""

import uuid
from typing import Callable

from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
)
from app.db.models.user import User
from app.domain.refresh_token_repository import RefreshTokenRepository


class InvalidRefreshToken(Exception):
    """Signature/expiry/type/store lookup failed — route maps to 401."""


class RefreshTokenReuse(InvalidRefreshToken):
    """A revoked token was replayed; its family has been revoked."""


class AuthTokenService:
    def __init__(
        self,
        repo: RefreshTokenRepository,
        *,
        get_user: Callable[[int], User | None],
    ):
        self.repo = repo
        self.get_user = get_user

    def issue_pair(self, user_id: int) -> tuple[str, str]:
        """New login: start a fresh family and issue the first pair."""
        family_id = uuid.uuid4().hex
        return self._issue(user_id=user_id, family_id=family_id)

    def rotate(self, refresh_token: str) -> tuple[str, str]:
        """Validate a refresh token and rotate it to a new pair."""
        payload = self._decode_refresh(refresh_token)
        jti = payload.get("jti")
        if not jti:
            raise InvalidRefreshToken("missing token id")

        record = self.repo.get(jti=jti)
        if record is None:
            # Unknown jti: never issued, or pruned. Treat as invalid.
            raise InvalidRefreshToken("unknown token")

        if record.revoked:
            # Reuse of a rotated/revoked token → assume compromise and
            # burn the whole family so the attacker AND victim are cut off.
            self.repo.revoke_family(family_id=record.family_id)
            raise RefreshTokenReuse("refresh token reuse detected")

        user = self.get_user(record.user_id)
        if user is None or not user.is_active:
            self.repo.revoke_family(family_id=record.family_id)
            raise InvalidRefreshToken("user not found or inactive")

        # Single-use: retire the presented token, issue its successor.
        self.repo.revoke(jti=jti)
        return self._issue(user_id=record.user_id, family_id=record.family_id)

    def revoke_session(self, refresh_token: str) -> None:
        """Logout: revoke the whole family. Best-effort — an already
        invalid token is a no-op, never an error."""
        try:
            payload = self._decode_refresh(refresh_token)
        except InvalidRefreshToken:
            return
        record = self.repo.get(jti=payload.get("jti", ""))
        if record is not None:
            self.repo.revoke_family(family_id=record.family_id)

    # --- internals -------------------------------------------------
    def _issue(self, *, user_id: int, family_id: str) -> tuple[str, str]:
        jti = uuid.uuid4().hex
        refresh_token, expires_at = create_refresh_token(str(user_id), jti=jti)
        self.repo.create(
            jti=jti,
            family_id=family_id,
            user_id=user_id,
            expires_at=expires_at,
        )
        return create_access_token(subject=str(user_id)), refresh_token

    def _decode_refresh(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise InvalidRefreshToken("bad signature or expired") from exc
        if payload.get("type") != "refresh" or payload.get("sub") is None:
            raise InvalidRefreshToken("wrong token type")
        return payload

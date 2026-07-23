from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

# Precomputed at import: verified against when a login email is unknown, so
# an absent account costs the same bcrypt time as a present one. Without
# this, "no such user" returns in ~1 ms while a real verify takes ~200 ms —
# a timing oracle that confirms which emails are registered (OWASP A07).
_DUMMY_VERIFY_HASH = pwd_context.hash("constant-time-login-placeholder")


def hash_password(password: str) -> str:
    """
    Hash a plain-text password.
    """
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password too long")
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    """
    return pwd_context.verify(password, hashed_password)


def dummy_verify(password: str) -> None:
    """Burn one bcrypt verification and discard the result.

    Call this on the login path when the email is unknown, so the response
    time matches a real credential check and can't be used to enumerate
    which accounts exist.
    """
    pwd_context.verify(password, _DUMMY_VERIFY_HASH)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a short-lived JWT access token (type claim: "access").
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": subject,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str, *, jti: str) -> tuple[str, datetime]:
    """
    Create a long-lived JWT refresh token (type claim: "refresh").

    Carries a unique `jti` so the server-side store can rotate and
    revoke it. Only /auth/refresh accepts it; the type claim keeps a
    leaked refresh token from being replayed as an API credential and
    an access token from minting new sessions. Returns the token and
    its absolute expiry (the store records the latter).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": jti,
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM), expire

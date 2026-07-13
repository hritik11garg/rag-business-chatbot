from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cookies import ACCESS_COOKIE
from app.core.security import ALGORITHM
from app.db.models.user import User
from app.db.session import SessionLocal


def get_db():
    """
    Provides a database session per request.
    Ensures proper cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_token_service(db: Session = Depends(get_db)):
    """Refresh-token service, composed here so routes depend on the
    abstraction and tests can override it without a database."""
    from app.infrastructure.db.refresh_token_repository import (
        DBRefreshTokenRepository,
    )
    from app.use_cases.auth_tokens import AuthTokenService

    return AuthTokenService(
        DBRefreshTokenRepository(db),
        get_user=lambda uid: db.query(User).filter(User.id == uid).first(),
    )


# auto_error=False: a missing Authorization header is not an error here —
# we fall back to the access-token cookie (browser transport) before deciding.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates the JWT and returns the current user.

    Accepts the access token from the Authorization header (programmatic
    clients) OR the httpOnly access-token cookie (browser). The header
    wins when both are present, so a Bearer credential is always honored
    as sent.
    """
    if token is None:
        token = request.cookies.get(ACCESS_COOKIE)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        user_id: str | None = payload.get("sub")

        if user_id is None or payload.get("type") != "access":
            # refresh tokens are only valid at /auth/refresh — a
            # long-lived token must never work as an API credential
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Function-level authorization (OWASP A01): a valid session is not
    enough to mutate the shared knowledge base. Any active member may
    read and chat; only an admin may add or remove source documents,
    because those documents are what every member of the org queries.

    Layers on top of get_current_user, so authentication (who you are)
    stays separate from authorization (what you may do). Admin power is
    implicitly org-scoped: the user carries their own organization_id,
    so an admin can only act within their own tenant.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user

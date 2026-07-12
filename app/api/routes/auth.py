from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_token_service
from app.api.schemas.auth import RefreshRequest, SignupRequest, TokenResponse
from app.api.schemas.common import MessageResponse
from app.core.config import settings
from app.core.ratelimit import limiter
from app.core.security import verify_password
from app.db.models.user import User
from app.use_cases.auth_tokens import AuthTokenService, InvalidRefreshToken
from app.use_cases.signup_organization import (
    EmailAlreadyRegisteredError,
    SignupOrganizationUseCase,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def signup(request: Request, data: SignupRequest, db: Session = Depends(get_db)):
    use_case = SignupOrganizationUseCase(db)
    try:
        return use_case.execute(
            organization_name=data.organization_name,
            email=data.email,
            password=data.password,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tokens: AuthTokenService = Depends(get_token_service),
):
    """OAuth2-compatible login: verify credentials, start a new refresh
    family, and issue the first access+refresh pair."""
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access, refresh = tokens.issue_pair(user.id)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(
    request: Request,
    data: RefreshRequest,
    tokens: AuthTokenService = Depends(get_token_service),
):
    """Rotate a valid refresh token for a fresh pair. A replayed
    (already-rotated) token revokes the whole family — see
    AuthTokenService. All failures collapse to a single opaque 401 so
    the client can't distinguish 'unknown' from 'reused' from 'expired'."""
    try:
        access, refresh_token = tokens.rotate(data.refresh_token)
    except InvalidRefreshToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def logout(
    request: Request,
    data: RefreshRequest,
    tokens: AuthTokenService = Depends(get_token_service),
):
    """Revoke the presented refresh token's entire family. Idempotent:
    an already-invalid token still returns 200 (nothing to leak)."""
    tokens.revoke_session(data.refresh_token)
    return MessageResponse(message="Logged out")

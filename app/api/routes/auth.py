from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas.auth import RefreshRequest, SignupRequest, TokenResponse
from app.api.schemas.common import MessageResponse
from app.core.config import settings
from app.core.ratelimit import limiter
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.db.models.user import User
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
):
    """
    OAuth2-compatible login endpoint.
    """

    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(request: Request, data: RefreshRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a fresh access + refresh pair
    (rotation). Access tokens are rejected here, exactly mirroring how
    refresh tokens are rejected everywhere else.
    """
    try:
        payload = jwt.decode(
            data.refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh" or payload.get("sub") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )

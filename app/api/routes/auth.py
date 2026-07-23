import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_token_service
from app.api.schemas.auth import RefreshRequest, SignupRequest, TokenResponse
from app.api.schemas.common import MessageResponse
from app.core.config import settings
from app.core.cookies import (
    CSRF_COOKIE,
    CSRF_HEADER,
    REFRESH_COOKIE,
    clear_auth_cookies,
    new_csrf_token,
    set_auth_cookies,
)
from app.core.ratelimit import limiter
from app.core.security import dummy_verify, verify_password
from app.db.models.user import User
from app.use_cases.auth_tokens import AuthTokenService, InvalidRefreshToken
from app.use_cases.signup_organization import (
    EmailAlreadyRegisteredError,
    SignupOrganizationUseCase,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _csrf_ok(request: Request) -> bool:
    """Double-submit check: the X-CSRF-Token header must equal the
    csrf_token cookie. A cross-site attacker can auto-send the cookie but
    cannot read it to forge the header, so a forged request fails here."""
    header = request.headers.get(CSRF_HEADER)
    cookie = request.cookies.get(CSRF_COOKIE)
    return bool(header) and bool(cookie) and secrets.compare_digest(header, cookie)


def _resolve_refresh_token(request: Request, data: RefreshRequest | None) -> str | None:
    """Take the refresh token from the request body (programmatic client)
    or, failing that, the httpOnly cookie (browser). The cookie path is
    ambient-credential territory, so it must carry a valid CSRF token;
    the body path is an explicit credential and needs none."""
    body_token = data.refresh_token if data else None
    if body_token:
        return body_token

    cookie_token = request.cookies.get(REFRESH_COOKIE)
    if cookie_token and not _csrf_ok(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
    return cookie_token


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
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    tokens: AuthTokenService = Depends(get_token_service),
):
    """OAuth2-compatible login: verify credentials, start a new refresh
    family, and issue the first access+refresh pair.

    The pair is set as httpOnly cookies for the browser AND returned in
    the body for programmatic clients (dual transport). A fresh csrf
    token is minted for the double-submit defense."""
    user = db.query(User).filter(User.email == form_data.username).first()

    # Constant-time: an unknown email still pays the bcrypt cost, so the
    # response time can't reveal whether the account exists (OWASP A07).
    # Both branches return the same opaque message.
    if not user:
        dummy_verify(form_data.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access, refresh = tokens.issue_pair(user.id)
    set_auth_cookies(response, access=access, refresh=refresh, csrf=new_csrf_token())
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    tokens: AuthTokenService = Depends(get_token_service),
):
    """Rotate a valid refresh token for a fresh pair. The token comes from
    the body or the httpOnly cookie (CSRF-checked for the cookie path). A
    replayed (already-rotated) token revokes the whole family — see
    AuthTokenService. All failures collapse to a single opaque 401 so the
    client can't distinguish 'unknown' from 'reused' from 'expired'."""
    presented = _resolve_refresh_token(request, data)
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    try:
        access, refresh_token = tokens.rotate(presented)
    except InvalidRefreshToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc
    set_auth_cookies(
        response, access=access, refresh=refresh_token, csrf=new_csrf_token()
    )
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def logout(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    tokens: AuthTokenService = Depends(get_token_service),
):
    """Revoke the presented refresh token's entire family and clear the
    browser cookies. Idempotent: an already-invalid (or absent) token
    still returns 200 (nothing to leak). The cookie path is CSRF-checked
    so a forged cross-site request can't log the user out."""
    presented = _resolve_refresh_token(request, data)
    if presented:
        tokens.revoke_session(presented)
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out")

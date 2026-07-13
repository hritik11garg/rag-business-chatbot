"""Auth-cookie helpers for the browser transport (OWASP A05/A07).

The browser keeps its tokens in httpOnly+Secure+SameSite=Strict cookies
so JavaScript can never read them — a stored-XSS payload can no longer
exfiltrate a session the way it could from localStorage. Because cookies
are sent automatically, a readable csrf_token cookie backs a double-submit
CSRF defense (see the CSRF check in app.main and the auth routes).

Cookie names are exported so the routes, the CSRF check and the tests all
share one source of truth.
"""

import secrets

from fastapi import Response

from app.core.config import settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

# The refresh token is only ever presented to the auth endpoints, so its
# cookie is scoped to /auth — it never rides along on chat/document calls,
# shrinking where a leaked cookie could be replayed.
REFRESH_COOKIE_PATH = "/auth"


def new_csrf_token() -> str:
    """A high-entropy value for the double-submit cookie/header pair."""
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    response: Response, *, access: str, refresh: str, csrf: str
) -> None:
    """Attach the session cookies. `secure` follows is_production so local
    HTTP dev still works while production requires TLS. SameSite=Strict
    stops the browser sending them on any cross-site request."""
    secure = settings.is_production
    access_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=access_max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=refresh_max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )
    # Deliberately NOT httpOnly: the SPA must read this to echo it back in
    # the X-CSRF-Token header. It carries no authority on its own.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=refresh_max_age,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire all three cookies (must match the paths they were set with)."""
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")

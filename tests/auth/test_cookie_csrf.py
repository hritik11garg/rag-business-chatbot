"""Browser transport: httpOnly auth cookies + double-submit CSRF (A05/A07).

These exercise the cookie path that the SPA uses, alongside the existing
Bearer/body tests. TestClient keeps a cookie jar, so once /login sets the
cookies they ride along on later requests exactly like a real browser.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_token_service
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from app.core.ratelimit import limiter
from app.core.security import hash_password
from app.db.models.user import User
from app.main import app
from app.use_cases.auth_tokens import AuthTokenService
from tests.auth.fakes import FakeRefreshTokenRepository

PASSWORD = "correct-horse"
HASHED = hash_password(PASSWORD)


def make_user() -> User:
    return User(
        id=1,
        email="user@example.com",
        hashed_password=HASHED,
        organization_id=1,
        is_active=True,
        is_admin=True,
    )


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *a, **k):
        return self

    def first(self):
        return self.user


class FakeDB:
    def __init__(self, user):
        self.user = user

    def query(self, model):
        return FakeQuery(self.user)


@pytest.fixture()
def client():
    repo = FakeRefreshTokenRepository()
    app.dependency_overrides[get_db] = lambda: FakeDB(make_user())
    app.dependency_overrides[get_token_service] = lambda: AuthTokenService(
        repo, get_user=lambda uid: make_user()
    )
    limiter.reset()
    # raise_server_exceptions=False: the CSRF gate runs before routing, so
    # a passed gate on /chat lands in the (unmocked) pipeline and 500s. We
    # only assert on the gate (403 vs not), so let the 500 be a response
    # rather than propagate.
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    limiter.reset()


def login(client):
    return client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": PASSWORD},
    )


def test_login_sets_httponly_auth_cookies_and_readable_csrf(client):
    resp = login(client)
    assert resp.status_code == 200
    set_cookie = " ".join(resp.headers.get_list("set-cookie")).lower()
    # access + refresh are httpOnly; csrf is deliberately readable by JS
    assert f"{ACCESS_COOKIE}=" in set_cookie and "httponly" in set_cookie
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.cookies.get(REFRESH_COOKIE)
    assert client.cookies.get(CSRF_COOKIE)


def test_cookie_authenticates_api_request_without_bearer(client):
    login(client)
    # No Authorization header — the access cookie carries the session.
    resp = client.get("/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


def test_state_change_via_cookie_without_csrf_is_forbidden(client):
    login(client)
    # Cookie-authed POST to an app route with no X-CSRF-Token -> 403.
    resp = client.post("/chat", json={"question": "hi", "top_k": 5})
    assert resp.status_code == 403


def test_state_change_via_cookie_with_matching_csrf_passes_gate(client):
    login(client)
    csrf = client.cookies.get(CSRF_COOKIE)
    resp = client.post(
        "/chat",
        json={"question": "hi", "top_k": 5},
        headers={CSRF_HEADER: csrf},
    )
    # The CSRF gate is cleared; whatever the downstream use case returns,
    # it must not be the 403 that a missing/invalid token produces.
    assert resp.status_code != 403


def test_forged_csrf_header_is_rejected(client):
    login(client)
    resp = client.post(
        "/chat",
        json={"question": "hi", "top_k": 5},
        headers={CSRF_HEADER: "not-the-real-token"},
    )
    assert resp.status_code == 403


def test_refresh_via_cookie_requires_csrf(client):
    login(client)
    # Browser refresh: no body, cookie present, but no CSRF header -> 403.
    resp = client.post("/auth/refresh")
    assert resp.status_code == 403

    # With the matching header it rotates and re-sets cookies.
    csrf = client.cookies.get(CSRF_COOKIE)
    ok = client.post("/auth/refresh", headers={CSRF_HEADER: csrf})
    assert ok.status_code == 200


def test_logout_via_cookie_clears_cookies(client):
    login(client)
    csrf = client.cookies.get(CSRF_COOKIE)
    resp = client.post("/auth/logout", headers={CSRF_HEADER: csrf})
    assert resp.status_code == 200
    # Server sent expiring Set-Cookie headers; the jar drops them.
    assert not client.cookies.get(ACCESS_COOKIE)
    assert not client.cookies.get(REFRESH_COOKIE)


def test_bearer_request_is_csrf_exempt_even_with_cookies(client):
    # A Bearer client is immune to CSRF; the gate must not block it even
    # when a cookie jar is also present.
    access = login(client).json()["access_token"]
    resp = client.post(
        "/chat",
        json={"question": "hi", "top_k": 5},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code != 403

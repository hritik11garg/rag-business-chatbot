"""Auth flow: login, refresh rotation, token-type separation, 429s.

Endpoint-level tests via TestClient with the DB dependency overridden —
no Postgres needed. The limiter is reset per test so rate-limit state
never leaks between tests (all TestClient requests share one IP).
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db, get_token_service
from app.core.config import settings
from app.core.ratelimit import limiter
from app.core.security import create_access_token, hash_password
from app.db.models.user import User
from app.main import app
from app.use_cases.auth_tokens import AuthTokenService
from tests.auth.fakes import FakeRefreshTokenRepository

PASSWORD = "correct-horse"
# bcrypt is deliberately slow — hash once for the whole module.
HASHED = hash_password(PASSWORD)


def make_user() -> User:
    return User(
        id=1,
        email="user@example.com",
        hashed_password=HASHED,
        organization_id=1,
        is_active=True,
    )


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *args, **kwargs):
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
    # One repo instance across the request lifecycle so rotation state
    # (issued -> revoked) persists between /login and /refresh calls.
    repo = FakeRefreshTokenRepository()
    app.dependency_overrides[get_db] = lambda: FakeDB(make_user())
    app.dependency_overrides[get_token_service] = lambda: AuthTokenService(
        repo, get_user=lambda uid: make_user()
    )
    limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.reset()


def login(client):
    return client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": PASSWORD},
    )


def test_login_returns_access_and_refresh(client):
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_is_401(client):
    response = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_refresh_rotates_the_pair(client):
    refresh_token = login(client).json()["refresh_token"]
    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != refresh_token  # rotated


def test_replayed_refresh_token_is_rejected(client):
    r1 = login(client).json()["refresh_token"]
    client.post("/auth/refresh", json={"refresh_token": r1})  # rotate once
    replay = client.post("/auth/refresh", json={"refresh_token": r1})
    assert replay.status_code == 401


def test_logout_then_refresh_is_rejected(client):
    r1 = login(client).json()["refresh_token"]
    assert client.post("/auth/logout", json={"refresh_token": r1}).status_code == 200
    after = client.post("/auth/refresh", json={"refresh_token": r1})
    assert after.status_code == 401


def test_access_token_rejected_at_refresh(client):
    access_token = login(client).json()["access_token"]
    response = client.post("/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


def test_refresh_token_rejected_as_api_credential(client):
    refresh_token = login(client).json()["refresh_token"]
    response = client.get("/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


def test_access_token_accepted_as_api_credential(client):
    access_token = login(client).json()["access_token"]
    response = client.get("/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_legacy_token_without_type_claim_is_rejected(client):
    # Tokens minted before the type claim existed must not keep working.
    legacy_like = create_access_token(subject="1")
    # simulate a pre-upgrade token by stripping the claim
    from jose import jwt

    from app.core.security import ALGORITHM

    payload = jwt.decode(legacy_like, settings.SECRET_KEY, algorithms=[ALGORITHM])
    del payload["type"]
    stripped = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    response = client.get("/me", headers={"Authorization": f"Bearer {stripped}"})
    assert response.status_code == 401


@pytest.mark.skipif(
    not settings.RATE_LIMIT_ENABLED, reason="rate limiting disabled in this env"
)
def test_login_rate_limited_after_configured_burst(client):
    codes = [
        client.post(
            "/auth/login",
            data={"username": "user@example.com", "password": "wrong"},
        ).status_code
        for _ in range(12)
    ]
    assert 429 in codes

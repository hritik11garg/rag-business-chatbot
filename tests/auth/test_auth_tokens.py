"""AuthTokenService: rotation, single-use, reuse detection, logout.

These are the heart of the refresh-token security model, tested with an
in-memory repo (no DB, no HTTP)."""

import pytest

from app.db.models.user import User
from app.use_cases.auth_tokens import (
    AuthTokenService,
    InvalidRefreshToken,
    RefreshTokenReuse,
)
from tests.auth.fakes import FakeRefreshTokenRepository

# is_active must be set explicitly: SQLAlchemy's column default=True only
# applies on DB insert, so an in-memory User() has is_active=None.
ACTIVE_USER = User(
    id=1, email="u@x.com", hashed_password="x", organization_id=1, is_active=True
)


def make_service(repo=None, user=ACTIVE_USER):
    return AuthTokenService(
        repo or FakeRefreshTokenRepository(), get_user=lambda uid: user
    )


def test_issue_pair_records_one_token():
    repo = FakeRefreshTokenRepository()
    access, refresh = make_service(repo).issue_pair(1)
    assert access and refresh
    assert len(repo.records) == 1
    assert not next(iter(repo.records.values())).revoked


def test_rotate_revokes_old_and_issues_new():
    repo = FakeRefreshTokenRepository()
    service = make_service(repo)
    _, refresh = service.issue_pair(1)

    access2, refresh2 = service.rotate(refresh)
    assert access2 and refresh2 and refresh2 != refresh
    # old token now revoked, new token live, same family
    revoked = [r for r in repo.records.values() if r.revoked]
    live = [r for r in repo.records.values() if not r.revoked]
    assert len(revoked) == 1 and len(live) == 1
    assert revoked[0].family_id == live[0].family_id


def test_reuse_of_rotated_token_burns_the_whole_family():
    repo = FakeRefreshTokenRepository()
    service = make_service(repo)
    _, refresh = service.issue_pair(1)
    _, refresh2 = service.rotate(refresh)  # refresh now revoked

    # Attacker replays the OLD, already-rotated token.
    with pytest.raises(RefreshTokenReuse):
        service.rotate(refresh)

    # Every token in the family — including the legitimate refresh2 — dies.
    assert all(r.revoked for r in repo.records.values())
    with pytest.raises(InvalidRefreshToken):
        service.rotate(refresh2)


def test_rotate_unknown_token_is_invalid():
    # A validly-signed refresh token whose jti was never stored.
    from app.core.security import create_refresh_token

    token, _ = create_refresh_token("1", jti="never-stored")
    with pytest.raises(InvalidRefreshToken):
        make_service().rotate(token)


def test_rotate_rejects_access_token():
    from app.core.security import create_access_token

    with pytest.raises(InvalidRefreshToken):
        make_service().rotate(create_access_token(subject="1"))


def test_rotate_inactive_user_is_invalid_and_revokes_family():
    repo = FakeRefreshTokenRepository()
    inactive = User(
        id=1, email="u@x.com", hashed_password="x", organization_id=1, is_active=False
    )
    service = AuthTokenService(repo, get_user=lambda uid: inactive)
    # issue while "active" by using a service that sees the active user
    _, refresh = make_service(repo).issue_pair(1)

    with pytest.raises(InvalidRefreshToken):
        service.rotate(refresh)
    assert all(r.revoked for r in repo.records.values())


def test_logout_revokes_family_and_is_idempotent():
    repo = FakeRefreshTokenRepository()
    service = make_service(repo)
    _, refresh = service.issue_pair(1)

    service.revoke_session(refresh)
    assert all(r.revoked for r in repo.records.values())
    # second logout / garbage token: no error
    service.revoke_session(refresh)
    service.revoke_session("not-a-token")

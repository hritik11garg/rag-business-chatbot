"""Function-level authorization on the shared knowledge base (OWASP A01).

Any active member may read/chat; only an admin may mutate the corpus
(upload/delete). These tests pin the *authorization* boundary: a valid
non-admin session must be refused with 403 before any mutation runs.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db, require_admin
from app.core.ratelimit import limiter
from app.db.models.user import User
from app.main import app


def make_user(*, is_admin: bool) -> User:
    # is_active/is_admin set explicitly: SQLAlchemy column defaults only
    # apply on DB insert, so an in-memory User() leaves them None.
    return User(
        id=1,
        email="user@example.com",
        hashed_password="x",
        organization_id=1,
        is_active=True,
        is_admin=is_admin,
    )


# --- require_admin as a unit ------------------------------------------------


def test_require_admin_allows_admin():
    admin = make_user(is_admin=True)
    assert require_admin(current_user=admin) is admin


def test_require_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as exc:
        require_admin(current_user=make_user(is_admin=False))
    assert exc.value.status_code == 403


# --- endpoint gate: non-admin is refused before the mutation ----------------


@pytest.fixture()
def non_admin_client():
    # A dummy db that explodes if touched proves the 403 short-circuits
    # ahead of any use-case / database work.
    class Boom:
        def __getattr__(self, _):
            raise AssertionError("db must not be touched on a 403")

    app.dependency_overrides[get_current_user] = lambda: make_user(is_admin=False)
    app.dependency_overrides[get_db] = lambda: Boom()
    # Upload/delete now carry a tight per-IP limit; reset between tests so
    # rate-limit state can never leak in and turn a 403 assertion into 429.
    limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.reset()


def test_non_admin_cannot_delete_document(non_admin_client):
    resp = non_admin_client.delete("/documents/1")
    assert resp.status_code == 403


def test_non_admin_cannot_upload_document(non_admin_client):
    resp = non_admin_client.post(
        "/documents/upload",
        files={"file": ("x.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert resp.status_code == 403


def test_member_can_still_list_documents():
    # Reading is open to any member — the read route must NOT be gated.
    # A fake db that returns an empty result lets the request reach the
    # use case, proving the authorization layer let a non-admin through.
    class FakeQuery:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def all(self):
            return []

    class FakeDB:
        def query(self, *a, **k):
            return FakeQuery()

    app.dependency_overrides[get_current_user] = lambda: make_user(is_admin=False)
    app.dependency_overrides[get_db] = lambda: FakeDB()
    try:
        resp = TestClient(app).get("/documents")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.clear()

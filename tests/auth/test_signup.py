"""Signup: domain exception, org+admin creation, HTTP mapping."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.ratelimit import limiter
from app.db.models.organization import Organization
from app.db.models.user import User
from app.main import app
from app.use_cases.signup_organization import (
    EmailAlreadyRegisteredError,
    SignupOrganizationUseCase,
)


class FakeQuery:
    def __init__(self, existing_user):
        self.existing_user = existing_user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.existing_user


class FakeSession:
    """Fake session: flush() assigns ids the way a real flush would."""

    def __init__(self, existing_user=None):
        self.existing_user = existing_user
        self.added = []
        self.committed = False

    def query(self, model):
        return FakeQuery(self.existing_user)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = 1

    def commit(self):
        self.committed = True


def test_signup_creates_org_and_admin_user():
    db = FakeSession(existing_user=None)
    result = SignupOrganizationUseCase(db).execute(
        organization_name="acme", email="a@acme.com", password="pw"
    )

    orgs = [o for o in db.added if isinstance(o, Organization)]
    users = [u for u in db.added if isinstance(u, User)]
    assert len(orgs) == 1 and orgs[0].name == "acme"
    assert len(users) == 1
    assert users[0].is_admin is True
    assert users[0].organization_id == orgs[0].id
    assert users[0].hashed_password != "pw"  # stored hashed, never plain
    assert db.committed
    assert "message" in result


def test_signup_duplicate_email_raises_domain_error():
    existing = User(id=9, email="a@acme.com", hashed_password="x", organization_id=1)
    db = FakeSession(existing_user=existing)

    with pytest.raises(EmailAlreadyRegisteredError):
        SignupOrganizationUseCase(db).execute(
            organization_name="acme", email="a@acme.com", password="pw"
        )
    assert db.added == []  # fail fast: nothing half-created


def test_route_maps_duplicate_email_to_400():
    existing = User(id=9, email="a@acme.com", hashed_password="x", organization_id=1)
    app.dependency_overrides[get_db] = lambda: FakeSession(existing_user=existing)
    limiter.reset()
    try:
        client = TestClient(app)
        response = client.post(
            "/auth/signup",
            json={
                "organization_name": "acme",
                "email": "a@acme.com",
                "password": "pw",
            },
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Email already registered"
    finally:
        app.dependency_overrides.clear()
        limiter.reset()

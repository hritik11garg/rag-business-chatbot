"""Password policy is enforced at the schema edge (fail fast)."""

import pytest
from pydantic import ValidationError

from app.api.schemas.auth import PASSWORD_MAX, PASSWORD_MIN, SignupRequest


def valid(**overrides):
    data = {
        "organization_name": "acme",
        "email": "a@acme.com",
        "password": "a-good-password",
    }
    data.update(overrides)
    return data


def test_short_password_rejected():
    with pytest.raises(ValidationError):
        SignupRequest(**valid(password="x" * (PASSWORD_MIN - 1)))


def test_overlong_password_rejected():
    # Guards the bcrypt 72-byte truncation from being reachable.
    with pytest.raises(ValidationError):
        SignupRequest(**valid(password="x" * (PASSWORD_MAX + 1)))


def test_reasonable_password_accepted():
    req = SignupRequest(**valid(password="correct-horse-battery"))
    assert req.password == "correct-horse-battery"


def test_blank_org_name_rejected():
    with pytest.raises(ValidationError):
        SignupRequest(**valid(organization_name=""))

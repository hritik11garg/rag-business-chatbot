"""SECRET_KEY validation fails fast on weak keys (OWASP A02)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DB = "postgresql://x:y@localhost:5432/z"


def test_placeholder_secret_rejected_everywhere():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="YOUR_SECRET_KEY", ENV="development", DATABASE_URL=DB)


def test_empty_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="", ENV="development", DATABASE_URL=DB)


def test_short_secret_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="tooshort", ENV="production", DATABASE_URL=DB)


def test_short_secret_allowed_in_dev():
    s = Settings(SECRET_KEY="dev-throwaway", ENV="development", DATABASE_URL=DB)
    assert s.SECRET_KEY == "dev-throwaway"


def test_strong_secret_accepted_in_production():
    strong = "a" * 40
    s = Settings(SECRET_KEY=strong, ENV="production", DATABASE_URL=DB)
    assert s.SECRET_KEY == strong

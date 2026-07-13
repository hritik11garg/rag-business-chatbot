"""Interactive API docs are disabled in production (OWASP A05).

The docs expose the full API surface, so /docs, /redoc and /openapi.json
must 404 in production while staying available as a dev aid elsewhere.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import settings


@pytest.mark.parametrize(
    "env, expected",
    [
        ("production", True),
        ("PROD", True),
        ("development", False),
        ("staging", False),
    ],
)
def test_is_production_is_the_single_source_of_truth(env, expected):
    original = settings.ENV
    try:
        settings.ENV = env
        assert settings.is_production is expected
    finally:
        settings.ENV = original


def test_docs_served_in_development():
    # The app was built with the default (development) ENV.
    client = TestClient(main_module.app)
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_docs_disabled_in_production():
    original = settings.ENV
    settings.ENV = "production"
    try:
        # Rebuild the app under production settings; docs_url et al. are
        # read from settings.is_production at construction time.
        importlib.reload(main_module)
        client = TestClient(main_module.app)
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
    finally:
        settings.ENV = original
        importlib.reload(main_module)  # restore the dev app for other tests

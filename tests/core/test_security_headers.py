"""Security response headers, including CSP (OWASP A05).

CSP is the layer that contains an XSS if one ever lands: no inline script
execution, and no exfiltration to a foreign origin.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_baseline_hardening_headers_present():
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in headers


def test_csp_is_strict_on_app_routes():
    csp = client.get("/health").headers["Content-Security-Policy"]
    # No inline/eval escape hatches for script, and no foreign origins.
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp.split("style-src")[0]
    assert "unsafe-eval" not in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'none'" in csp


def test_docs_routes_are_exempt_so_swagger_still_loads():
    # Dev-only convenience: Swagger pulls its bundle from a CDN, which a
    # self-only CSP would block. Docs are disabled in production entirely.
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "Content-Security-Policy" not in resp.headers

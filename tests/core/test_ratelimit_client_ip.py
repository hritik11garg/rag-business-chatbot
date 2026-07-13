"""Rate-limit keying is proxy-aware but spoof-resistant (OWASP A04/A05).

The limiter must key on the true client IP even behind a proxy, without
letting a client forge X-Forwarded-For to escape its own bucket.
"""

import pytest

from app.core import ratelimit
from app.core.config import settings


class FakeClient:
    def __init__(self, host):
        self.host = host


class FakeRequest:
    def __init__(self, host="10.0.0.1", xff=None):
        self.client = FakeClient(host)
        self.headers = {} if xff is None else {"X-Forwarded-For": xff}


@pytest.fixture()
def proxy_count():
    original = settings.TRUSTED_PROXY_COUNT
    yield lambda n: setattr(settings, "TRUSTED_PROXY_COUNT", n)
    settings.TRUSTED_PROXY_COUNT = original


def test_direct_exposure_ignores_forwarded_header(proxy_count):
    proxy_count(0)
    # Even a present XFF must be ignored when we trust no proxies.
    req = FakeRequest(host="10.0.0.1", xff="9.9.9.9")
    assert ratelimit.client_ip(req) == "10.0.0.1"


def test_single_proxy_uses_forwarded_client(proxy_count):
    proxy_count(1)
    req = FakeRequest(host="10.0.0.1", xff="9.9.9.9")
    assert ratelimit.client_ip(req) == "9.9.9.9"


def test_client_cannot_spoof_extra_left_entries(proxy_count):
    proxy_count(1)
    # Attacker prepends a forged IP; the trusted proxy appended the real
    # one on the right, so the Nth-from-right pick ignores the forgery.
    req = FakeRequest(host="10.0.0.1", xff="6.6.6.6, 9.9.9.9")
    assert ratelimit.client_ip(req) == "9.9.9.9"


def test_two_proxies_reach_past_both_hops(proxy_count):
    proxy_count(2)
    req = FakeRequest(host="10.0.0.1", xff="1.2.3.4, 172.16.0.1")
    assert ratelimit.client_ip(req) == "1.2.3.4"


def test_missing_header_fails_safe_to_socket_peer(proxy_count):
    proxy_count(1)
    req = FakeRequest(host="10.0.0.1", xff=None)
    assert ratelimit.client_ip(req) == "10.0.0.1"


def test_too_few_hops_fails_safe_to_socket_peer(proxy_count):
    proxy_count(2)  # expect 2 hops, header only has 1 => spoof/misconfig
    req = FakeRequest(host="10.0.0.1", xff="9.9.9.9")
    assert ratelimit.client_ip(req) == "10.0.0.1"

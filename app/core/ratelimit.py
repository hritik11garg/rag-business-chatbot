"""Per-IP rate limiting (slowapi).

Counters are in-memory and per worker process — with N uvicorn workers
the effective ceiling is up to N x the configured limit. Good enough
to blunt brute-force and runaway clients; a multi-instance deployment
would point the limiter at Redis storage instead.

RATE_LIMIT_ENABLED=false turns it off entirely (the load benchmark
drives 50 users from one IP, which is exactly what this exists to
block in production).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def client_ip(request) -> str:
    """Rate-limit key: the real client IP, proxy-aware but spoof-resistant.

    With TRUSTED_PROXY_COUNT = N > 0 we take the Nth value from the RIGHT
    of X-Forwarded-For — the address the outermost *trusted* proxy actually
    recorded. A client can only prepend entries on the left, so it can
    never push a forged IP into that position. If the header is missing or
    has fewer than N hops (malformed / spoof attempt), we fail safe to the
    socket peer. With N = 0 (direct exposure) the header is ignored
    entirely and only the socket peer is used.
    """
    n = settings.TRUSTED_PROXY_COUNT
    if n > 0:
        forwarded = request.headers.get("X-Forwarded-For", "")
        hops = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(hops) >= n:
            return hops[-n]
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_ip,
    enabled=settings.RATE_LIMIT_ENABLED,
)

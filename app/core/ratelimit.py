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

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
)

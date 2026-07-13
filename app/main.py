import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import get_current_user
from app.api.routes import auth, documents, chat
from app.composition.singletons import get_embedding_service, get_llm_service
from app.core.config import settings
from app.core.logging import request_id_var, setup_logging
from app.core.ratelimit import limiter
from app.db import models  # noqa: F401
from app.db.models.user import User

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app")
request_logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler.
    Runs once on application startup and shutdown.
    """
    logger.info("app starting")
    # Warm the process-wide singletons so request #1 doesn't pay
    # the MiniLM model load (~4s) or the LLM client construction.
    get_embedding_service()
    get_llm_service()
    logger.info("models warmed, ready to serve")
    yield
    logger.info("app shutting down")


# Interactive API docs map the entire attack surface, so they are
# disabled in production (OWASP A05: Security Misconfiguration). They
# stay on in dev/staging where they're a development aid, not exposure.
_docs_disabled = settings.is_production
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _docs_disabled else "/docs",
    redoc_url=None if _docs_disabled else "/redoc",
    openapi_url=None if _docs_disabled else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Baseline hardening headers on every response (OWASP A05).

    X-Content-Type-Options stops MIME sniffing; X-Frame-Options +
    frame-ancestors stop clickjacking; Referrer-Policy stops URL
    leakage; Permissions-Policy drops powerful browser features the
    API never needs. HSTS is opt-in (TLS-only) via settings.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    if settings.ENABLE_HSTS:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains",
        )
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Assign a correlation ID to every request (honoring an inbound
    X-Request-ID from a proxy), expose it on the response, and emit one
    structured line per request with method/path/status/duration."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path != "/health":  # keep probes out of the logs
            request_logger.info(
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                },
            )
        return response
    except Exception:
        request_logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        raise
    finally:
        request_id_var.reset(token)


@app.get("/health", tags=["system"])
def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {"status": "ok"}


@app.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    """
    Test protected endpoint.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "organization_id": current_user.organization_id,
    }


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)

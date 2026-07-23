from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# HS256 auth security rests entirely on this key's secrecy and entropy.
# These obvious placeholders must never boot the app in ANY environment.
_PLACEHOLDER_SECRETS = {"", "YOUR_SECRET_KEY", "changeme", "secret", "change-me"}
_MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Business Knowledge Base Chatbot"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate limiting (per client IP; in-memory per worker process)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_CHAT: str = "30/minute"
    # Uploads are the most expensive endpoint (parse + embed every chunk +
    # one LLM call per chunk for FAQ generation), so they get their own,
    # much tighter budget than chat.
    RATE_LIMIT_UPLOAD: str = "5/minute"

    # Number of trusted reverse-proxy hops in front of the app. 0 (default)
    # = directly exposed: use the socket peer IP and IGNORE X-Forwarded-For
    # (a client could otherwise spoof it to dodge rate limits). Set to the
    # real hop count (e.g. 1 behind a single nginx/ALB) so the limiter keys
    # on the true client IP the trusted proxy recorded, not the proxy's IP.
    TRUSTED_PROXY_COUNT: int = 0

    # Uploads — cap read into memory; content-type headers are
    # client-controlled, so size + magic-byte check are the pre-parse
    # defenses (see UploadDocumentUseCase)
    MAX_UPLOAD_MB: int = 25

    # Abuse controls on the ingestion pipeline. Rate limiting bounds
    # requests per minute; these bound the damage of the requests that do
    # get through — total corpus size per tenant, and how many LLM calls a
    # single upload can amplify into (one FAQ call per chunk otherwise).
    MAX_DOCUMENTS_PER_ORG: int = 1000
    MAX_FAQ_CHUNKS: int = 50

    # Send HSTS only when the app is actually served over TLS (behind a
    # TLS-terminating proxy in prod); leave off for plain-HTTP local dev.
    ENABLE_HSTS: bool = False

    # Database
    DATABASE_URL: str

    # Background jobs (Celery)
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # LLM provider: openai | groq | gemini | ollama | anthropic
    LLM_PROVIDER: str = "openai"

    # Optional overrides — unset means "use the provider's default"
    LLM_MODEL: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_TEMPERATURE: float = 0.1

    # Cap on generated tokens. A grounded RAG answer is short, so bounding
    # output length bounds the p95 latency tail (unbounded generation is
    # what lets a verbose answer blow past the latency budget) and caps the
    # per-request token cost. Raise it if answers get truncated.
    LLM_MAX_TOKENS: int = 512

    # Retrieval fan-out (single source of truth for the whole chat path —
    # request schema default, use-case defaults, and the SQL LIMIT). Higher
    # top_k trades prompt cost and latency for recall; MAX bounds what a
    # client may request so nobody can pull the whole corpus as context.
    DEFAULT_TOP_K: int = 5
    MAX_TOP_K: int = 20

    # API keys — only the one matching LLM_PROVIDER is required
    # (ollama runs locally and needs no key)
    OPENAI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def is_production(self) -> bool:
        """Single source of truth for 'is this a production deployment?' —
        drives the SECRET_KEY length floor and prod-only hardening such as
        disabling the interactive API docs."""
        return self.ENV.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        """Fail fast on a weak signing key (OWASP A02).

        A placeholder key is rejected everywhere — booting with it means
        anyone who has read the public example file can forge tokens. The
        length floor is enforced in production, where a too-short key is
        a real forgery risk; dev/CI may use shorter throwaway keys.
        """
        if self.SECRET_KEY in _PLACEHOLDER_SECRETS:
            raise ValueError(
                "SECRET_KEY is a placeholder — set a real random secret "
                '(python -c "import secrets; print(secrets.token_hex(32))")'
            )
        if self.is_production and len(self.SECRET_KEY) < _MIN_SECRET_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_LEN} characters "
                "in production"
            )
        return self


settings = Settings()

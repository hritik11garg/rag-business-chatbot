from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Uploads — cap read into memory; content-type headers are
    # client-controlled, so size is the only pre-parse defense
    MAX_UPLOAD_MB: int = 25

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

    # API keys — only the one matching LLM_PROVIDER is required
    # (ollama runs locally and needs no key)
    OPENAI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Business Knowledge Base Chatbot"
    ENV: str = "development"

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str

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

    class Config:
        env_file = ".env"


settings = Settings()

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

    # LLM
    # LLM_PROVIDER: str = "gemini"
    # OPENAI_API_KEY: str | None = None
    # GEMINI_API_KEY: str | None = None
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()

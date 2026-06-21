from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://rag:ragpassword@postgres:5432/ragdb"
    redis_url: str = "redis://redis:6379/0"
    api_env: str = "development"
    log_level: str = "debug"
    secret_key: str = "changeme"
    billing_url: str = "http://billing:8004"
    notification_url: str = "http://notification:8005"
    app_url: str = "http://localhost:3001"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_url: str = "http://localhost:8000/auth/oauth/google/callback"
    frontend_url: str = "http://localhost"

    # SMTP (for invite emails)
    smtp_host: str = "postfix"
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@chatbot-app.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

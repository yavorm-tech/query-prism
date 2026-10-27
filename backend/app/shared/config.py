from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Datastores
    database_url: str = "postgresql+asyncpg://rag@postgres:5432/ragdb"
    redis_url: str = "redis://redis:6379/0"                # answer cache + rate limits (LRU eviction)
    celery_broker_url: str = "redis://redis-broker:6379/0"  # task queue (noeviction, AOF)
    neo4j_url: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str                  # required: set NEO4J_PASSWORD

    # AI providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    embedding_dims: int = 3072
    embedding_batch_size: int = 100

    # Runtime
    api_env: str = "development"
    log_level: str = "info"
    secret_key: str                      # required: signs and verifies JWTs
    app_name: str = "QueryPrism"
    app_url: str = "http://localhost:3001"
    frontend_url: str = "http://localhost"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_url: str = "http://localhost:8000/auth/oauth/google/callback"

    # Email
    smtp_host: str = "postfix"
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@chatbot-app.com"
    sales_email: str = ""

    # Ingestion
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 500
    chunk_size: int = 512
    chunk_overlap: int = 50

    @field_validator("secret_key")
    @classmethod
    def _require_strong_secret(cls, v: str) -> str:
        if v == "changeme" or len(v) < 32:
            raise ValueError("must be set to a random value of at least 32 characters")
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

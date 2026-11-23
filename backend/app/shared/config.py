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

    # Answer tiers (ADR-008): ordered provider:model routes, tried in turn on provider errors
    llm_tier_basic: str = "openai:gpt-4o-mini,anthropic:claude-haiku-4-5-20251001"
    llm_tier_standard: str = "anthropic:claude-haiku-4-5-20251001,openai:gpt-4o-mini"
    llm_tier_premium: str = "anthropic:claude-sonnet-4-6,openai:gpt-4o"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 1

    # Sessions (ADR-009): short access JWT + rotating refresh token in an httpOnly cookie
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    refresh_cookie_secure: bool | None = None   # None: Secure when frontend_url is https

    # Browser origins allowed to call the API with credentials (comma-separated).
    # Empty: FRONTEND_URL and APP_URL, plus local Vite/dev ports when API_ENV=development.
    cors_origins: str = ""

    @property
    def cors_allow_origins(self) -> list[str]:
        if self.cors_origins.strip():
            return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        origins = {self.frontend_url.rstrip("/"), self.app_url.rstrip("/")}
        if self.api_env == "development":
            origins |= {f"http://localhost:{p}" for p in (80, 3000, 3001, 5173)}
        return sorted(origins)

    @property
    def refresh_cookie_is_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.frontend_url.startswith("https://")

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
    # Upload storage between api and worker: "local" (shared volume) or "s3" (any S3-compatible store)
    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_prefix: str = "uploads"
    s3_endpoint_url: str = ""          # e.g. http://minio:9000; empty for AWS
    s3_region: str = ""
    s3_access_key_id: str = ""         # empty: the default AWS credential chain
    s3_secret_access_key: str = ""
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

from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://rag:ragpassword@postgres:5432/ragdb"
    redis_url: str = "redis://redis:6379/0"
    neo4j_url: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str                  # required: set NEO4J_PASSWORD
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_api_key: str = ""
    api_env: str = "development"
    log_level: str = "debug"
    secret_key: str                      # required: signs and verifies JWTs
    internal_api_token: str              # required: authenticates service-to-service calls
    billing_url: str = "http://billing:8004"
    embedding_model: str = "text-embedding-3-large"
    embedding_dims: int = 3072
    embedding_batch_size: int = 100

    @field_validator("secret_key", "internal_api_token")
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

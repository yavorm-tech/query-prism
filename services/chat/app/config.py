from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://rag:ragpassword@postgres:5432/ragdb"
    redis_url: str = "redis://redis:6379/0"
    neo4j_url: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ragpassword"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    cohere_api_key: str = ""
    api_env: str = "development"
    log_level: str = "debug"
    secret_key: str = "changeme"
    billing_url: str = "http://billing:8004"
    embedding_model: str = "text-embedding-3-large"
    embedding_dims: int = 3072
    embedding_batch_size: int = 100

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

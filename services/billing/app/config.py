from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://rag:ragpassword@postgres:5432/ragdb"
    api_env: str = "development"
    log_level: str = "debug"
    secret_key: str = "changeme"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

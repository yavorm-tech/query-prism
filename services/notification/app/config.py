from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    api_env: str = "development"
    log_level: str = "debug"
    secret_key: str = "changeme"
    smtp_host: str = "postfix"
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    sales_email: str = ""
    app_name: str = "QueryPrism"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

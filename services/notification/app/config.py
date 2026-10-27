from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    api_env: str = "development"
    log_level: str = "debug"
    secret_key: str                      # required: signs and verifies JWTs
    internal_api_token: str              # required: authenticates service-to-service calls
    smtp_host: str = "postfix"
    smtp_port: int = 25
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    sales_email: str = ""
    app_name: str = "QueryPrism"

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

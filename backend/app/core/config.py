from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Crypto AI Trader"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = Field(default="postgresql+asyncpg://trader:trader@postgres:5432/trader")
    redis_url: str = Field(default="redis://redis:6379/0")

    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    encryption_key: str = Field(default="P9YpxIBJHW2FQ1NpoZ4jdECrgXqNRmn78DS97L5yOAk=")

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    default_exchange: str = "binance"
    paper_trading: bool = True
    log_retention_days: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()

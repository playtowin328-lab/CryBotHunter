from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
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
    live_trading_enabled: bool = False
    exchange_sandbox_enabled: bool = True
    allow_live_trading_without_sandbox: bool = False
    market_data_mode: str = "paper"
    paper_fee_rate: float = 0.0004
    paper_slippage_bps: float = 2.0
    exchange_api_key: str | None = None
    exchange_secret_key: str | None = None
    exchange_passphrase: str | None = None
    log_retention_days: int = 90
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: list[int] = Field(default_factory=list)
    trader_loop_seconds: int = 60
    llm_provider: str = "none"
    openai_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: int = 20
    trading_panic_key: str = "trading:panic"
    guard_min_trades: int = 5
    guard_min_win_rate: float = 35.0
    guard_max_loss_streak: int = 3
    guard_min_total_profit: float = -50.0
    ai_committee_enabled: bool = True
    ai_committee_min_consensus: float = 0.66
    max_gross_exposure_percent: float = 300.0
    max_symbol_exposure_percent: float = 100.0
    candle_ingest_symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"])
    candle_ingest_timeframes: list[str] = Field(default_factory=lambda: ["1h"])
    candle_ingest_limit: int = 500
    candle_ingest_loop_seconds: int = 300
    candle_dataset_target: int = 100_000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("telegram_allowed_chat_ids", mode="before")
    @classmethod
    def parse_telegram_chat_ids(cls, value: Any) -> list[int]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("candle_ingest_symbols", "candle_ingest_timeframes", mode="before")
    @classmethod
    def parse_csv_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


def async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def sync_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

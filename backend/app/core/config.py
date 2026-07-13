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

    cors_origins_raw: str = Field(default="http://localhost:5173,http://localhost:8080", validation_alias="CORS_ORIGINS")
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
    telegram_allowed_chat_ids_raw: str = Field(default="", validation_alias="TELEGRAM_ALLOWED_CHAT_IDS")
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
    pretrade_quality_enabled: bool = True
    pretrade_quality_min_candles: int = 420
    pretrade_quality_min_profit_factor: float = 1.1
    pretrade_quality_min_win_rate: float = 42.0
    pretrade_quality_min_profitable_windows_percent: float = 50.0
    pretrade_quality_min_trades: int = 3
    pretrade_quality_min_risk_multiplier: float = 0.35
    market_quality_min_quote_volume: float = 100_000_000.0
    market_quality_max_spread_bps: float = 25.0
    market_quality_max_price_change_percent: float = 18.0
    market_quality_min_risk_multiplier: float = 0.5
    strategy_optimizer_apply_enabled: bool = True
    strategy_optimizer_min_profit_factor: float = 1.05
    strategy_optimizer_min_trades: int = 3
    strategy_optimizer_max_age_days: int = 14
    strategy_optimizer_worker_enabled: bool = True
    strategy_optimizer_loop_seconds: int = 21600
    strategy_optimizer_refresh_hours: int = 24
    strategy_optimizer_limit: int = 800
    strategy_optimizer_top_n: int = 5
    candle_ingest_symbols_raw: str = Field(default="BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT", validation_alias="CANDLE_INGEST_SYMBOLS")
    candle_ingest_timeframes_raw: str = Field(default="1h", validation_alias="CANDLE_INGEST_TIMEFRAMES")
    candle_ingest_limit: int = 500
    candle_ingest_loop_seconds: int = 300
    candle_dataset_target: int = 100_000

    @property
    def cors_origins(self) -> list[str]:
        return _parse_csv(self.cors_origins_raw)

    @property
    def telegram_allowed_chat_ids(self) -> list[int]:
        return [int(item) for item in _parse_csv(self.telegram_allowed_chat_ids_raw)]

    @property
    def candle_ingest_symbols(self) -> list[str]:
        return _parse_csv(self.candle_ingest_symbols_raw)

    @property
    def candle_ingest_timeframes(self) -> list[str]:
        return _parse_csv(self.candle_ingest_timeframes_raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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

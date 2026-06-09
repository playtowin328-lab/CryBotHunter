from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SettingsIn(BaseModel):
    exchange: Literal["binance", "bybit", "okx", "kucoin"] = "binance"
    api_key: str | None = None
    secret_key: str | None = None
    passphrase: str | None = None
    risk_percent: float = Field(ge=0.1, le=10)
    daily_risk_percent: float = Field(ge=0.1, le=25)
    max_positions: int = Field(ge=1, le=50)
    min_rating: int = Field(ge=0, le=100)
    scan_interval: Literal["1m", "5m", "15m", "1h"]
    stop_loss_percent: float = Field(ge=0.1, le=25)
    take_profit_percent: float = Field(ge=0.1, le=100)


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exchange: str
    api_key_masked: str | None = None
    secret_key_masked: str | None = None
    passphrase_masked: str | None = None
    risk_percent: float
    daily_risk_percent: float
    max_positions: int
    min_rating: int
    scan_interval: str
    stop_loss_percent: float
    take_profit_percent: float


class MarketCoin(BaseModel):
    symbol: str
    price: float
    volume_24h: float
    price_change_percent: float
    atr: float
    rsi: float
    ema20: float
    ema50: float
    ema200: float
    macd: float
    funding_rate: float = 0
    open_interest: float = 0
    rating: int


class StrategySignal(BaseModel):
    symbol: str
    signal: Literal["BUY", "SELL", "WAIT"]
    score: int
    reasons: list[str] = []


class TradingDecision(BaseModel):
    symbol: str
    signal: Literal["BUY", "SELL", "WAIT"]
    score: int
    action: Literal["OPENED", "SKIPPED"]
    reason: str


class TradingRunOut(BaseModel):
    scanned: int
    opened: int
    skipped: int
    decisions: list[TradingDecision]


class SystemStatusOut(BaseModel):
    paper_trading: bool
    exchange: str
    telegram_enabled: bool
    telegram_chat_count: int
    open_positions: int
    daily_pnl: float


class BacktestOut(BaseModel):
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    average_profit: float
    average_loss: float


class ActionMessage(BaseModel):
    ok: bool
    message: str


class MlPrediction(BaseModel):
    symbol: str
    long_probability: int
    short_probability: int


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    side: str
    entry_price: float
    current_price: float
    volume: float
    stop: float
    take: float
    pnl: float
    status: str
    entered_at: datetime


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    message: str
    created_at: datetime


class DashboardOut(BaseModel):
    balance: float
    pnl_day: float
    pnl_week: float
    win_rate: float
    trades_count: int
    active_positions: list[PositionOut]

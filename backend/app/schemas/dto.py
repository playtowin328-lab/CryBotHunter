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
    trailing_stop_percent: float = Field(default=0.8, ge=0, le=20)
    atr_stop_multiplier: float = Field(default=1.5, ge=0.1, le=10)
    risk_reward_ratio: float = Field(default=2.0, ge=0.2, le=20)
    breakeven_trigger_r: float = Field(default=1.0, ge=0.1, le=10)
    breakeven_offset_percent: float = Field(default=0.05, ge=0, le=5)


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
    trailing_stop_percent: float
    atr_stop_multiplier: float
    risk_reward_ratio: float
    breakeven_trigger_r: float
    breakeven_offset_percent: float


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


class PositionUpdateOut(BaseModel):
    id: int
    symbol: str
    side: str
    previous_price: float
    current_price: float
    pnl: float
    status: str
    exit_reason: str | None = None
    stop: float
    take: float


class TradingTickOut(BaseModel):
    checked: int
    closed: int
    updated: list[PositionUpdateOut]


class SystemStatusOut(BaseModel):
    paper_trading: bool
    exchange: str
    telegram_enabled: bool
    telegram_chat_count: int
    open_positions: int
    daily_pnl: float
    panic_paused: bool = False
    panic_reason: str | None = None
    ai_committee_enabled: bool = True
    ai_committee_min_consensus: float = 0.66
    gross_exposure: float = 0
    gross_exposure_percent: float = 0
    max_gross_exposure_percent: float = 300
    max_symbol_exposure_percent: float = 100


class PerformanceGuardOut(BaseModel):
    allowed: bool
    reason: str
    trades_checked: int
    win_rate: float
    loss_streak: int
    total_profit: float


class BacktestOut(BaseModel):
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    average_profit: float
    average_loss: float
    trades_count: int = 0
    total_profit: float = 0


class HistoryIngestOut(BaseModel):
    symbol: str
    timeframe: str
    inserted: int


class StrategyOptimizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    symbol: str
    timeframe: str
    parameters: dict
    score: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    total_profit: float
    trades_count: int
    created_at: datetime | None = None


class ActionMessage(BaseModel):
    ok: bool
    message: str


class AgentDecisionOut(BaseModel):
    agent_name: str
    symbol: str
    action: Literal["BUY", "SELL", "WAIT", "ALLOW", "REDUCE_SIZE", "BLOCK"]
    confidence: float
    rationale: str
    context: dict = Field(default_factory=dict)


class LlmAdvice(BaseModel):
    action: Literal["BUY", "SELL", "WAIT"]
    confidence: float = Field(ge=0, le=1)
    rationale: str
    invalid_if: list[str] = []


class AgentAnalysisOut(BaseModel):
    symbol: str
    market: AgentDecisionOut
    llm: AgentDecisionOut | None = None
    risk: AgentDecisionOut
    committee: list[AgentDecisionOut] = Field(default_factory=list)
    consensus_score: float = 0
    final_action: Literal["BUY", "SELL", "WAIT", "BLOCK"]
    final_confidence: float
    approved: bool


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
    initial_risk: float
    breakeven_applied: bool
    breakeven_trigger_r: float
    breakeven_offset_percent: float
    trailing_stop_percent: float
    highest_price: float
    lowest_price: float
    pnl: float
    status: str
    exit_reason: str | None = None
    entered_at: datetime
    closed_at: datetime | None = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exchange_order_id: str | None = None
    symbol: str
    side: str
    order_type: str
    status: str
    requested_amount: float
    filled_amount: float
    requested_price: float | None = None
    average_price: float | None = None
    fee: float
    slippage: float
    created_at: datetime


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

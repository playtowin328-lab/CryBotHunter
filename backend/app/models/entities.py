from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False)


class UserSettings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    exchange: Mapped[str] = mapped_column(String(32), default="binance")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    secret_key_encrypted: Mapped[str | None] = mapped_column(Text)
    passphrase_encrypted: Mapped[str | None] = mapped_column(Text)
    risk_percent: Mapped[float] = mapped_column(Float, default=1.0)
    daily_risk_percent: Mapped[float] = mapped_column(Float, default=3.0)
    max_positions: Mapped[int] = mapped_column(Integer, default=3)
    min_rating: Mapped[int] = mapped_column(Integer, default=80)
    scan_interval: Mapped[str] = mapped_column(String(16), default="5m")
    stop_loss_percent: Mapped[float] = mapped_column(Float, default=1.5)
    take_profit_percent: Mapped[float] = mapped_column(Float, default=3.0)
    trailing_stop_percent: Mapped[float] = mapped_column(Float, default=0.8)
    atr_stop_multiplier: Mapped[float] = mapped_column(Float, default=1.5)
    risk_reward_ratio: Mapped[float] = mapped_column(Float, default=2.0)
    breakeven_trigger_r: Mapped[float] = mapped_column(Float, default=1.0)
    breakeven_offset_percent: Mapped[float] = mapped_column(Float, default=0.05)
    partial_take_profit_r: Mapped[float] = mapped_column(Float, default=1.0)
    partial_close_percent: Mapped[float] = mapped_column(Float, default=50.0)

    user: Mapped[User] = relationship(back_populates="settings")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    take: Mapped[float] = mapped_column(Float)
    initial_risk: Mapped[float] = mapped_column(Float, default=0.0)
    breakeven_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    breakeven_trigger_r: Mapped[float] = mapped_column(Float, default=1.0)
    breakeven_offset_percent: Mapped[float] = mapped_column(Float, default=0.05)
    partial_take_profit_r: Mapped[float] = mapped_column(Float, default=1.0)
    partial_close_percent: Mapped[float] = mapped_column(Float, default=50.0)
    partial_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    trailing_stop_percent: Mapped[float] = mapped_column(Float, default=0.0)
    highest_price: Mapped[float] = mapped_column(Float, default=0.0)
    lowest_price: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    entry_context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default=PositionStatus.OPEN.value)
    exit_reason: Mapped[str | None] = mapped_column(String(32))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trades: Mapped[list["Trade"]] = relationship(back_populates="position")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    position: Mapped[Position | None] = relationship(back_populates="trades")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.NEW.value)
    requested_amount: Mapped[float] = mapped_column(Float)
    filled_amount: Mapped[float] = mapped_column(Float, default=0.0)
    requested_price: Mapped[float | None] = mapped_column(Float)
    average_price: Mapped[float | None] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_candle_symbol_timeframe_timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    signal: Mapped[str] = mapped_column(String(8))
    score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StrategyOptimization(Base):
    __tablename__ = "strategy_optimizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    total_profit: Mapped[float] = mapped_column(Float, default=0.0)
    trades_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearningRule(Base):
    __tablename__ = "learning_rules"
    __table_args__ = (UniqueConstraint("scope", "side", "feature_key", "feature_value", name="uq_learning_rule"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), index=True, default="GLOBAL")
    side: Mapped[str] = mapped_column(String(8), index=True)
    feature_key: Mapped[str] = mapped_column(String(64), index=True)
    feature_value: Mapped[str] = mapped_column(String(128), index=True)
    penalty: Mapped[float] = mapped_column(Float, default=0.0)
    observations: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    total_profit: Mapped[float] = mapped_column(Float, default=0.0)
    last_reason: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LogEntry(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

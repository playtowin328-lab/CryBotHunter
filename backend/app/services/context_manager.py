from __future__ import annotations

import asyncio
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import get_settings


MARKET_CONTEXT_FEATURES = ("rsi", "atr", "sma_trend")


class MarketDataError(ValueError):
    """Raised when exchange candles cannot produce a safe market context."""


@dataclass(frozen=True)
class MarketContext:
    close: float
    rsi: float
    atr: float
    sma: float
    normalized_rsi: float
    normalized_atr: float
    normalized_sma_trend: float

    @property
    def state_vector(self) -> list[float]:
        """Stable-Baselines-friendly float vector with every value in [-1, 1]."""
        return [
            self.normalized_rsi,
            self.normalized_atr,
            self.normalized_sma_trend,
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "features": list(MARKET_CONTEXT_FEATURES),
            "state_vector": self.state_vector,
            "raw": {
                "close": self.close,
                "rsi": self.rsi,
                "atr": self.atr,
                "sma": self.sma,
            },
            "normalized": {
                "rsi": self.normalized_rsi,
                "atr": self.normalized_atr,
                "sma_trend": self.normalized_sma_trend,
            },
        }


@dataclass(frozen=True)
class TradeMemoryRecord:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    exit_reason: str
    timestamp: datetime


class TradeMemory:
    """Non-blocking SQLite mirror of completed trades used as local bot memory."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self._write_lock = asyncio.Lock()

    async def record(self, trade: TradeMemoryRecord) -> int:
        self._validate_trade(trade)
        async with self._write_lock:
            return await asyncio.to_thread(self._record_sync, trade)

    async def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 10_000))
        return await asyncio.to_thread(self._recent_sync, safe_limit)

    def _record_sync(self, trade: TradeMemoryRecord) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO trades (symbol, side, entry_price, exit_price, pnl, exit_reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.symbol,
                    trade.side,
                    trade.entry_price,
                    trade.exit_price,
                    trade.pnl,
                    trade.exit_reason,
                    trade.timestamp.astimezone(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def _recent_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, symbol, side, entry_price, exit_price, pnl, exit_reason, timestamp
                FROM trades
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                pnl REAL NOT NULL,
                exit_reason TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        return connection

    def _validate_trade(self, trade: TradeMemoryRecord) -> None:
        if not trade.symbol.strip() or not trade.side.strip() or not trade.exit_reason.strip():
            raise ValueError("Trade memory fields cannot be empty")
        for name in ("entry_price", "exit_price", "pnl"):
            value = float(getattr(trade, name))
            if not math.isfinite(value) or (name != "pnl" and value <= 0):
                raise ValueError(f"Invalid trade {name}: {value}")
        if trade.timestamp.tzinfo is None:
            raise ValueError("Trade timestamp must be timezone-aware")


class ContextManager:
    def __init__(
        self,
        trade_memory: TradeMemory | None = None,
        rsi_period: int = 14,
        atr_period: int = 14,
        sma_period: int = 50,
        atr_normalization_ceiling: float = 0.10,
    ) -> None:
        settings = get_settings()
        self.trade_memory = trade_memory or TradeMemory(settings.trade_memory_sqlite_path)
        self.rsi_period = max(int(rsi_period), 2)
        self.atr_period = max(int(atr_period), 2)
        self.sma_period = max(int(sma_period), 2)
        self.atr_normalization_ceiling = max(float(atr_normalization_ceiling), 1e-6)

    async def get_market_context(self, candles: pd.DataFrame) -> MarketContext:
        """Calculate RSI, ATR and SMA outside the asyncio event-loop thread."""
        if not isinstance(candles, pd.DataFrame):
            raise MarketDataError("Candles must be provided as a pandas DataFrame")
        return await asyncio.to_thread(self._calculate_market_context, candles.copy(deep=True))

    def from_values(self, close: float, rsi: float, atr: float, sma: float) -> MarketContext:
        values = {"close": close, "rsi": rsi, "atr": atr, "sma": sma}
        for name, value in values.items():
            if value is None or not math.isfinite(float(value)):
                raise MarketDataError(f"Market context contains invalid {name}")
        close = float(close)
        rsi = float(rsi)
        atr = float(atr)
        sma = float(sma)
        if close <= 0 or atr < 0 or sma <= 0:
            raise MarketDataError("Market prices and volatility must be non-negative")

        normalized_rsi = float(np.clip((rsi - 50.0) / 50.0, -1.0, 1.0))
        atr_ratio = atr / close
        normalized_atr = float(np.clip((atr_ratio / self.atr_normalization_ceiling) * 2.0 - 1.0, -1.0, 1.0))
        trend_scale = max(atr * 3.0, close * 0.001)
        normalized_sma_trend = float(np.clip((close - sma) / trend_scale, -1.0, 1.0))
        return MarketContext(
            close=round(close, 8),
            rsi=round(float(np.clip(rsi, 0.0, 100.0)), 8),
            atr=round(atr, 8),
            sma=round(sma, 8),
            normalized_rsi=round(normalized_rsi, 8),
            normalized_atr=round(normalized_atr, 8),
            normalized_sma_trend=round(normalized_sma_trend, 8),
        )

    async def remember_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        exit_reason: str,
        timestamp: datetime | None = None,
    ) -> int:
        return await self.trade_memory.record(
            TradeMemoryRecord(
                symbol=symbol,
                side=side,
                entry_price=float(entry_price),
                exit_price=float(exit_price),
                pnl=float(pnl),
                exit_reason=exit_reason,
                timestamp=timestamp or datetime.now(timezone.utc),
            )
        )

    def _calculate_market_context(self, candles: pd.DataFrame) -> MarketContext:
        required_columns = {"high", "low", "close"}
        missing = required_columns.difference(candles.columns)
        if missing:
            raise MarketDataError(f"Missing candle columns: {', '.join(sorted(missing))}")

        frame = candles[["high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
        minimum_rows = max(self.rsi_period + 1, self.atr_period + 1, self.sma_period)
        if len(frame) < minimum_rows:
            raise MarketDataError(f"At least {minimum_rows} valid candles are required")
        if (frame[["high", "low", "close"]] <= 0).any().any() or (frame["high"] < frame["low"]).any():
            raise MarketDataError("Candles contain invalid prices")

        close = frame["close"]
        delta = close.diff()
        average_gain = delta.clip(lower=0).ewm(alpha=1 / self.rsi_period, adjust=False, min_periods=self.rsi_period).mean()
        average_loss = -delta.clip(upper=0).ewm(alpha=1 / self.rsi_period, adjust=False, min_periods=self.rsi_period).mean()
        relative_strength = average_gain / average_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + relative_strength))
        rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100.0)
        rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50.0)

        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - close.shift()).abs(),
                (frame["low"] - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.ewm(alpha=1 / self.atr_period, adjust=False, min_periods=self.atr_period).mean()
        sma = close.rolling(self.sma_period, min_periods=self.sma_period).mean()

        latest = (close.iloc[-1], rsi.iloc[-1], atr.iloc[-1], sma.iloc[-1])
        if any(pd.isna(value) or not math.isfinite(float(value)) for value in latest):
            raise MarketDataError("Latest candle cannot produce finite indicators")
        return self.from_values(close=latest[0], rsi=latest[1], atr=latest[2], sma=latest[3])

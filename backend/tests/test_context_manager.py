from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.services.context_manager import ContextManager, MarketDataError, TradeMemory


def candles(rows: int = 80) -> pd.DataFrame:
    close = np.linspace(100.0, 120.0, rows) + np.sin(np.arange(rows))
    return pd.DataFrame(
        {
            "high": close + 1.5,
            "low": close - 1.5,
            "close": close,
            "volume": np.full(rows, 1000.0),
        }
    )


@pytest.mark.asyncio
async def test_market_context_returns_bounded_rl_vector():
    context = await ContextManager().get_market_context(candles())

    assert 0 <= context.rsi <= 100
    assert context.atr > 0
    assert context.sma > 0
    assert len(context.state_vector) == 3
    assert all(-1 <= value <= 1 for value in context.state_vector)
    assert context.as_dict()["features"] == ["rsi", "atr", "sma_trend"]


@pytest.mark.asyncio
async def test_market_context_drops_exchange_data_holes_when_enough_rows_remain():
    frame = candles()
    frame.loc[10, "close"] = np.nan

    context = await ContextManager().get_market_context(frame)

    assert all(np.isfinite(value) for value in context.state_vector)


@pytest.mark.asyncio
async def test_market_context_rejects_insufficient_or_invalid_candles():
    with pytest.raises(MarketDataError, match="valid candles"):
        await ContextManager().get_market_context(candles(20))

    invalid = candles()
    invalid.loc[79, "high"] = None
    invalid.loc[79, "low"] = None
    invalid.loc[79, "close"] = None
    context = await ContextManager().get_market_context(invalid)
    assert np.isfinite(context.atr)


@pytest.mark.asyncio
async def test_trade_memory_writes_complete_trade_to_sqlite(tmp_path):
    memory = TradeMemory(tmp_path / "memory.sqlite3")
    manager = ContextManager(trade_memory=memory)

    trade_id = await manager.remember_trade(
        symbol="BTC/USDT",
        side="LONG",
        entry_price=100,
        exit_price=110,
        pnl=10,
        exit_reason="TAKE_PROFIT",
        timestamp=datetime(2026, 7, 15, tzinfo=timezone.utc),
    )
    rows = await memory.recent()

    assert trade_id == 1
    assert rows == [
        {
            "id": 1,
            "symbol": "BTC/USDT",
            "side": "LONG",
            "entry_price": 100.0,
            "exit_price": 110.0,
            "pnl": 10.0,
            "exit_reason": "TAKE_PROFIT",
            "timestamp": "2026-07-15T00:00:00+00:00",
        }
    ]

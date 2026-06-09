from datetime import datetime, timedelta, timezone

from app.models.entities import Candle
from app.services.backtesting import BacktestingService


def candles(count: int = 260):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    items = []
    price = 100.0
    for index in range(count):
        close = price * (1 + (0.004 if index % 5 else -0.002))
        items.append(
            Candle(
                symbol="BTC/USDT",
                timeframe="1h",
                timestamp=start + timedelta(hours=index),
                open=price,
                high=max(price, close) * 1.01,
                low=min(price, close) * 0.99,
                close=close,
                volume=100_000 + index,
            )
        )
        price = close
    return items


def test_backtest_returns_report_for_candles():
    report = BacktestingService().run(candles())
    assert report.trades_count >= 0
    assert report.win_rate >= 0
    assert report.max_drawdown >= 0

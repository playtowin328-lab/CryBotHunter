from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.history import HistoricalDataService
from app.services.market_scanner import MarketScanner


class PagedExchange:
    def __init__(self) -> None:
        self.calls: list[tuple[int | None, int]] = []

    async def fetch_ohlcv(self, _symbol, timeframe="1h", limit=250, since=None):
        self.calls.append((since, limit))
        start = since or 1_000_000
        interval = 3_600_000 if timeframe == "1h" else 60_000
        return [[start + index * interval, 1, 2, 0.5, 1.5, 100] for index in range(limit)]


def test_paper_market_data_value_is_real_feed_compatibility_alias():
    assert Settings(_env_file=None, market_data_mode="paper").uses_live_market_data is True
    assert Settings(_env_file=None, market_data_mode="ccxt").uses_live_market_data is True
    assert Settings(_env_file=None, market_data_mode="synthetic").uses_live_market_data is False


@pytest.mark.asyncio
async def test_history_fetches_multiple_real_market_pages():
    exchange = PagedExchange()
    service = HistoricalDataService(exchange)

    candles = await service._fetch_ccxt_pages("BTC/USDT", "1h", 2_500)

    assert len(candles) == 2_500
    assert [limit for _, limit in exchange.calls] == [1_000, 1_000, 500]
    assert candles == sorted(candles, key=lambda item: item[0])


@pytest.mark.asyncio
async def test_real_scanner_does_not_hide_exchange_failure(monkeypatch):
    class FailingExchange:
        async def fetch_tickers(self, _symbols):
            raise RuntimeError("exchange unavailable")

    monkeypatch.setattr("app.services.market_scanner.get_settings", lambda: SimpleNamespace(uses_live_market_data=True))

    with pytest.raises(RuntimeError, match="exchange unavailable"):
        await MarketScanner(FailingExchange()).scan(["BTC/USDT"])

import asyncio
from typing import Any

import ccxt

from app.core.config import get_settings


class ExchangeClient:
    def __init__(self, exchange: str | None = None) -> None:
        self.settings = get_settings()
        self.exchange = exchange or self.settings.default_exchange

    async def get_balance(self) -> dict[str, float]:
        if self.settings.paper_trading or not self.settings.live_trading_enabled:
            return {"USDT": 1000.0}
        client = self._client(authenticated=True)
        balance = await asyncio.to_thread(client.fetch_balance)
        return {asset: float(amount) for asset, amount in balance.get("total", {}).items() if amount}

    async def fetch_tickers(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        client = self._client(authenticated=False)
        tickers = await asyncio.to_thread(client.fetch_tickers, symbols)
        return {symbol: tickers[symbol] for symbol in symbols if symbol in tickers}

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 250) -> list[list[float]]:
        client = self._client(authenticated=False)
        return await asyncio.to_thread(client.fetch_ohlcv, symbol, timeframe, None, limit)

    async def create_order(self, symbol: str, side: str, amount: float, order_type: str = "market") -> dict[str, str | float]:
        if self.settings.paper_trading:
            return {"id": f"paper-{symbol}-{side}", "symbol": symbol, "side": side, "amount": amount, "type": order_type}
        if not self.settings.live_trading_enabled:
            raise RuntimeError("Live trading is disabled. Set LIVE_TRADING_ENABLED=true only after paper validation.")
        client = self._client(authenticated=True)
        return await asyncio.to_thread(client.create_order, symbol, order_type, side, amount)

    def _client(self, authenticated: bool) -> ccxt.Exchange:
        exchange_class = getattr(ccxt, self.exchange)
        params: dict[str, Any] = {"enableRateLimit": True, "options": {"defaultType": "swap"}}
        if authenticated:
            if not self.settings.exchange_api_key or not self.settings.exchange_secret_key:
                raise RuntimeError("Exchange API credentials are not configured")
            params["apiKey"] = self.settings.exchange_api_key
            params["secret"] = self.settings.exchange_secret_key
            if self.settings.exchange_passphrase:
                params["password"] = self.settings.exchange_passphrase
        return exchange_class(params)

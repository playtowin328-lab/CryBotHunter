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

    async def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        client_order_id: str | None = None,
        reduce_only: bool = False,
    ) -> dict[str, str | float]:
        if self.settings.paper_trading:
            return {"id": f"paper-{symbol}-{side}", "symbol": symbol, "side": side, "amount": amount, "type": order_type}
        if not self.settings.live_trading_enabled:
            raise RuntimeError("Live trading is disabled. Set LIVE_TRADING_ENABLED=true only after paper validation.")
        self._assert_live_safety()
        client = self._client(authenticated=True)
        params = self._order_params(client_order_id=client_order_id, reduce_only=reduce_only)
        return await asyncio.to_thread(client.create_order, symbol, order_type, side, amount, None, params)

    async def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        if self.settings.paper_trading:
            return {"id": order_id, "symbol": symbol, "status": "closed"}
        if not self.settings.live_trading_enabled:
            raise RuntimeError("Live trading is disabled.")
        self._assert_live_safety()
        client = self._client(authenticated=True)
        return await asyncio.to_thread(client.fetch_order, order_id, symbol)

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
        client = exchange_class(params)
        if self.settings.exchange_sandbox_enabled and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)
        return client

    def _assert_live_safety(self) -> None:
        if self.settings.exchange_sandbox_enabled:
            return
        if self.settings.allow_live_trading_without_sandbox:
            return
        raise RuntimeError("Live exchange execution without sandbox is blocked by safety policy.")

    def _order_params(self, client_order_id: str | None = None, reduce_only: bool = False) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if client_order_id:
            params["clientOrderId"] = client_order_id
            if self.exchange == "bybit":
                params["orderLinkId"] = client_order_id
        if reduce_only:
            params["reduceOnly"] = True
        return params

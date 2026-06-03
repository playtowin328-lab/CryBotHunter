from app.core.config import get_settings


class ExchangeClient:
    def __init__(self, exchange: str | None = None) -> None:
        self.exchange = exchange or get_settings().default_exchange

    async def get_balance(self) -> dict[str, float]:
        if get_settings().paper_trading:
            return {"USDT": 1000.0}
        raise NotImplementedError("Live CCXT balance retrieval must be configured with encrypted API keys.")

    async def create_order(self, symbol: str, side: str, amount: float, order_type: str = "market") -> dict[str, str | float]:
        if get_settings().paper_trading:
            return {"id": f"paper-{symbol}-{side}", "symbol": symbol, "side": side, "amount": amount, "type": order_type}
        raise NotImplementedError("Live CCXT trading is intentionally disabled until credentials are configured.")

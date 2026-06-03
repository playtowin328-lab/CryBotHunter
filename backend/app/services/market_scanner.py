from random import Random

import pandas as pd

from app.schemas.dto import MarketCoin


class MarketScanner:
    def __init__(self) -> None:
        self._rng = Random(42)

    async def scan(self, symbols: list[str] | None = None) -> list[MarketCoin]:
        symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        rows = [self._synthetic_row(symbol) for symbol in symbols]
        return [MarketCoin(**row, rating=self.rate_coin(row)) for row in rows]

    def rate_coin(self, row: dict[str, float | str]) -> int:
        volume_score = min(float(row["volume_24h"]) / 2_000_000_000 * 20, 20)
        trend_score = 25 if row["ema50"] > row["ema200"] else 12
        volatility_score = max(0, 15 - abs(float(row["atr"]) / float(row["price"]) * 100 - 3) * 3)
        volume_growth_score = min(max(float(row["price_change_percent"]), 0) * 4, 20)
        liquidity_score = min(float(row["open_interest"]) / 1_000_000_000 * 20, 20)
        return int(round(volume_score + trend_score + volatility_score + volume_growth_score + liquidity_score))

    def calculate_indicators(self, candles: pd.DataFrame) -> pd.DataFrame:
        close = candles["close"]
        candles["ema20"] = close.ewm(span=20).mean()
        candles["ema50"] = close.ewm(span=50).mean()
        candles["ema200"] = close.ewm(span=200).mean()
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss.replace(0, pd.NA)
        candles["rsi"] = 100 - (100 / (1 + rs))
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        candles["macd"] = ema12 - ema26
        high_low = candles["high"] - candles["low"]
        high_close = (candles["high"] - close.shift()).abs()
        low_close = (candles["low"] - close.shift()).abs()
        candles["atr"] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
        return candles

    def _synthetic_row(self, symbol: str) -> dict[str, float | str]:
        base = {"BTC/USDT": 68000, "ETH/USDT": 3600, "SOL/USDT": 155, "BNB/USDT": 620}.get(symbol, 2.5)
        shift = self._rng.uniform(-0.04, 0.06)
        price = base * (1 + shift)
        ema200 = price * self._rng.uniform(0.94, 1.03)
        ema50 = price * self._rng.uniform(0.97, 1.04)
        return {
            "symbol": symbol,
            "price": round(price, 4),
            "volume_24h": self._rng.uniform(300_000_000, 3_000_000_000),
            "price_change_percent": shift * 100,
            "atr": price * self._rng.uniform(0.01, 0.05),
            "rsi": self._rng.uniform(28, 74),
            "ema20": price * self._rng.uniform(0.98, 1.02),
            "ema50": ema50,
            "ema200": ema200,
            "macd": self._rng.uniform(-20, 20),
            "funding_rate": self._rng.uniform(-0.02, 0.02),
            "open_interest": self._rng.uniform(200_000_000, 2_000_000_000),
        }

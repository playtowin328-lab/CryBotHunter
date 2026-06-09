from datetime import datetime, timezone
from hashlib import sha256
from random import Random

import pandas as pd

from app.core.config import get_settings
from app.schemas.dto import MarketCoin
from app.services.exchange import ExchangeClient


class MarketScanner:
    async def scan(self, symbols: list[str] | None = None) -> list[MarketCoin]:
        symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        if get_settings().market_data_mode.lower() == "ccxt":
            try:
                return await self._scan_ccxt(symbols)
            except Exception:
                pass
        rows = [self._synthetic_row(symbol) for symbol in symbols]
        return [MarketCoin(**row, rating=self.rate_coin(row)) for row in rows]

    async def _scan_ccxt(self, symbols: list[str]) -> list[MarketCoin]:
        exchange = ExchangeClient()
        tickers = await exchange.fetch_tickers(symbols)
        coins: list[MarketCoin] = []
        for symbol in symbols:
            candles = await exchange.fetch_ohlcv(symbol, timeframe="1h", limit=250)
            if len(candles) < 200:
                continue
            frame = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
            indicators = self.calculate_indicators(frame).iloc[-1]
            ticker = tickers.get(symbol, {})
            row = {
                "symbol": symbol,
                "price": float(ticker.get("last") or indicators["close"]),
                "volume_24h": float(ticker.get("quoteVolume") or frame.tail(24)["volume"].sum()),
                "price_change_percent": float(ticker.get("percentage") or 0),
                "atr": float(indicators["atr"] or 0),
                "rsi": float(indicators["rsi"] or 50),
                "ema20": float(indicators["ema20"]),
                "ema50": float(indicators["ema50"]),
                "ema200": float(indicators["ema200"]),
                "macd": float(indicators["macd"]),
                "funding_rate": 0.0,
                "open_interest": 0.0,
            }
            coins.append(MarketCoin(**row, rating=self.rate_coin(row)))
        return coins

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
        minute_bucket = int(datetime.now(timezone.utc).timestamp() // 60)
        digest = sha256(f"{symbol}:{minute_bucket}".encode()).hexdigest()
        rng = Random(int(digest[:12], 16))
        base = {"BTC/USDT": 68000, "ETH/USDT": 3600, "SOL/USDT": 155, "BNB/USDT": 620}.get(symbol, 2.5)
        shift = rng.uniform(-0.04, 0.06)
        price = base * (1 + shift)
        ema200 = price * rng.uniform(0.94, 1.03)
        ema50 = price * rng.uniform(0.97, 1.04)
        return {
            "symbol": symbol,
            "price": round(price, 4),
            "volume_24h": rng.uniform(300_000_000, 3_000_000_000),
            "price_change_percent": shift * 100,
            "atr": price * rng.uniform(0.01, 0.05),
            "rsi": rng.uniform(28, 74),
            "ema20": price * rng.uniform(0.98, 1.02),
            "ema50": ema50,
            "ema200": ema200,
            "macd": rng.uniform(-20, 20),
            "funding_rate": rng.uniform(-0.02, 0.02),
            "open_interest": rng.uniform(200_000_000, 2_000_000_000),
        }

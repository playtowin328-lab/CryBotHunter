from datetime import datetime, timedelta, timezone
from hashlib import sha256
from random import Random

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Candle
from app.services.exchange import ExchangeClient


class HistoricalDataService:
    async def ingest(self, db: AsyncSession, symbol: str, timeframe: str = "1h", limit: int = 500) -> int:
        candles = await self._fetch(symbol, timeframe, limit)
        if not candles:
            return 0
        rows = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": candle["timestamp"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
            }
            for candle in candles
        ]
        statement = insert(Candle).values(rows)
        statement = statement.on_conflict_do_nothing(
            constraint="uq_candle_symbol_timeframe_timestamp",
        )
        result = await db.execute(statement)
        await db.commit()
        return int(result.rowcount or 0)

    async def load(self, db: AsyncSession, symbol: str, timeframe: str = "1h", limit: int = 500) -> list[Candle]:
        result = await db.execute(
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def _fetch(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        if get_settings().market_data_mode.lower() == "ccxt":
            raw = await ExchangeClient().fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            return [
                {
                    "timestamp": datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                }
                for item in raw
            ]
        return self._paper_candles(symbol, timeframe, limit)

    def _paper_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}.get(timeframe, 60)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        base = {"BTC/USDT": 68000, "ETH/USDT": 3600, "SOL/USDT": 155, "BNB/USDT": 620}.get(symbol, 2.5)
        candles: list[dict] = []
        price = base
        for index in range(limit):
            timestamp = now - timedelta(minutes=minutes * (limit - index))
            digest = sha256(f"{symbol}:{timeframe}:{timestamp.isoformat()}".encode()).hexdigest()
            rng = Random(int(digest[:12], 16))
            drift = rng.uniform(-0.012, 0.014)
            open_price = price
            close = max(open_price * (1 + drift), 0.0001)
            high = max(open_price, close) * (1 + rng.uniform(0, 0.006))
            low = min(open_price, close) * (1 - rng.uniform(0, 0.006))
            volume = rng.uniform(10_000, 200_000)
            candles.append(
                {
                    "timestamp": timestamp,
                    "open": round(open_price, 6),
                    "high": round(high, 6),
                    "low": round(low, 6),
                    "close": round(close, 6),
                    "volume": round(volume, 6),
                }
            )
            price = close
        return candles

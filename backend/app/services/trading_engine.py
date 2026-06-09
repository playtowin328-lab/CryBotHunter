from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import LogEntry, Position, Signal, Trade
from app.schemas.dto import MarketCoin
from app.services.exchange import ExchangeClient
from app.services.market_scanner import MarketScanner
from app.services.risk_manager import RiskManager, RiskSettings
from app.services.strategy import StrategyCore
from app.services.telegram_bot import TelegramNotifier


class TradingEngine:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.strategy = StrategyCore()
        self.risk = RiskManager()
        self.exchange = ExchangeClient()
        self.telegram = TelegramNotifier()

    async def run_once(self, db: AsyncSession, settings: RiskSettings) -> list[Signal]:
        balance = (await self.exchange.get_balance()).get("USDT", settings.balance)
        coins = await self.scanner.scan()
        open_count = await self._open_positions_count(db)
        daily_pnl = await self._daily_pnl(db)
        created: list[Signal] = []

        for coin in sorted(coins, key=lambda item: item.rating, reverse=True):
            signal = self.strategy.evaluate(coin)
            db_signal = Signal(symbol=coin.symbol, signal=signal.signal, score=signal.score)
            db.add(db_signal)
            created.append(db_signal)

            accepted, reason = self.risk.can_open(signal, settings, open_count, daily_pnl)
            if accepted:
                await self._open_position(db, coin, signal.signal, balance, settings)
                open_count += 1
                db.add(LogEntry(level="INFO", message=f"Opened {signal.signal} paper position for {coin.symbol}"))
                await self.telegram.broadcast(f"Position opened: {signal.signal} {coin.symbol} score={signal.score}")
            else:
                db.add(LogEntry(level="INFO", message=f"Skipped {coin.symbol}: {reason}"))

        await db.commit()
        return created

    async def _open_position(self, db: AsyncSession, coin: MarketCoin, signal: str, balance: float, settings: RiskSettings) -> None:
        side = "LONG" if signal == "BUY" else "SHORT"
        stop = coin.price * (1 - settings.stop_loss_percent / 100) if side == "LONG" else coin.price * (1 + settings.stop_loss_percent / 100)
        take = coin.price * (1 + settings.take_profit_percent / 100) if side == "LONG" else coin.price * (1 - settings.take_profit_percent / 100)
        volume = self.risk.position_size(balance, settings.risk_percent, coin.price, stop)
        await self.exchange.create_order(coin.symbol, "buy" if side == "LONG" else "sell", volume)
        db.add(Position(symbol=coin.symbol, side=side, entry_price=coin.price, current_price=coin.price, volume=volume, stop=stop, take=take))
        db.add(Trade(symbol=coin.symbol, side=side, entry_price=coin.price, exit_price=None, profit=0))

    async def _open_positions_count(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
        return int(result.scalar_one())

    async def _daily_pnl(self, db: AsyncSession) -> float:
        result = await db.execute(select(func.coalesce(func.sum(Trade.profit), 0.0)))
        return float(result.scalar_one())

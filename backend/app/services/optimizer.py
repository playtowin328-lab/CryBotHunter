from itertools import product

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import StrategyOptimization
from app.schemas.dto import StrategyOptimizationOut
from app.services.backtesting import BacktestingService
from app.services.history import HistoricalDataService


class StrategyOptimizerService:
    def __init__(self) -> None:
        self.backtester = BacktestingService()
        self.history = HistoricalDataService()

    async def optimize(self, db: AsyncSession, symbol: str, timeframe: str = "1h", limit: int = 500, top_n: int = 5) -> list[StrategyOptimizationOut]:
        candles = await self.history.load(db, symbol=symbol, timeframe=timeframe, limit=limit)
        if len(candles) < 220:
            await self.history.ingest(db, symbol=symbol, timeframe=timeframe, limit=limit)
            candles = await self.history.load(db, symbol=symbol, timeframe=timeframe, limit=limit)

        candidates: list[StrategyOptimizationOut] = []
        stop_values = [1.0, 1.5, 2.0]
        take_values = [2.0, 3.0, 4.0]
        risk_values = [7.5, 10.0, 12.5]
        trailing_values = [0.0, 0.8, 1.2]

        for stop_loss, take_profit, risk_per_trade, trailing_stop in product(stop_values, take_values, risk_values, trailing_values):
            report = self.backtester.run(
                candles,
                risk_per_trade=risk_per_trade,
                stop_loss_percent=stop_loss,
                take_profit_percent=take_profit,
                trailing_stop_percent=trailing_stop,
            )
            score = self._score(report.total_profit, report.profit_factor, report.win_rate, report.max_drawdown, report.trades_count)
            candidates.append(
                StrategyOptimizationOut(
                    symbol=symbol,
                    timeframe=timeframe,
                    parameters={
                        "stop_loss_percent": stop_loss,
                        "take_profit_percent": take_profit,
                        "trailing_stop_percent": trailing_stop,
                        "risk_per_trade": risk_per_trade,
                    },
                    score=score,
                    win_rate=report.win_rate,
                    profit_factor=report.profit_factor,
                    max_drawdown=report.max_drawdown,
                    total_profit=report.total_profit,
                    trades_count=report.trades_count,
                )
            )

        top = sorted(candidates, key=lambda item: item.score, reverse=True)[:top_n]
        for item in top:
            db.add(
                StrategyOptimization(
                    symbol=item.symbol,
                    timeframe=item.timeframe,
                    parameters=item.parameters,
                    score=item.score,
                    win_rate=item.win_rate,
                    profit_factor=item.profit_factor,
                    max_drawdown=item.max_drawdown,
                    total_profit=item.total_profit,
                    trades_count=item.trades_count,
                )
            )
        await db.commit()
        return top

    async def recent(self, db: AsyncSession, limit: int = 20) -> list[StrategyOptimization]:
        result = await db.execute(select(StrategyOptimization).order_by(StrategyOptimization.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    def _score(self, total_profit: float, profit_factor: float, win_rate: float, max_drawdown: float, trades_count: int) -> float:
        if trades_count == 0:
            return -9999
        return round(total_profit + profit_factor * 20 + win_rate * 0.5 - max_drawdown * 1.2 + min(trades_count, 30), 4)

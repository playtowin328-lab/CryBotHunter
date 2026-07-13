from itertools import product
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import StrategyOptimization
from app.schemas.dto import StrategyOptimizationOut
from app.services.backtesting import BacktestingService
from app.services.history import HistoricalDataService
from app.services.risk_manager import RiskSettings


class StrategyOptimizerService:
    def __init__(self) -> None:
        self.settings = get_settings()
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

    async def best_for(self, db: AsyncSession, symbol: str, timeframe: str = "1h") -> StrategyOptimization | None:
        if not self.settings.strategy_optimizer_apply_enabled:
            return None
        optimization = await self._best_for_timeframe(db, symbol, timeframe)
        if optimization:
            return optimization
        if timeframe != "1h":
            return await self._best_for_timeframe(db, symbol, "1h")
        return None

    async def _best_for_timeframe(self, db: AsyncSession, symbol: str, timeframe: str) -> StrategyOptimization | None:
        result = await db.execute(
            select(StrategyOptimization)
            .where(
                StrategyOptimization.symbol == symbol,
                StrategyOptimization.timeframe == timeframe,
                StrategyOptimization.profit_factor >= self.settings.strategy_optimizer_min_profit_factor,
                StrategyOptimization.trades_count >= self.settings.strategy_optimizer_min_trades,
            )
            .order_by(StrategyOptimization.score.desc(), StrategyOptimization.created_at.desc())
            .limit(10)
        )
        for optimization in result.scalars().all():
            if self._is_fresh(optimization):
                return optimization
        return None

    def apply_to_risk_settings(self, settings: RiskSettings, optimization: StrategyOptimization) -> tuple[RiskSettings, str]:
        parameters = optimization.parameters or {}
        stop_loss = self._positive_float(parameters.get("stop_loss_percent"), settings.stop_loss_percent)
        take_profit = self._positive_float(parameters.get("take_profit_percent"), settings.take_profit_percent)
        trailing_stop = self._bounded_float(parameters.get("trailing_stop_percent"), settings.trailing_stop_percent, minimum=0.0, maximum=20.0)
        risk_reward_ratio = max(settings.min_risk_reward_ratio, round(take_profit / stop_loss, 4)) if stop_loss > 0 else settings.risk_reward_ratio
        optimized = replace(
            settings,
            stop_loss_percent=stop_loss,
            take_profit_percent=take_profit,
            trailing_stop_percent=trailing_stop,
            risk_reward_ratio=risk_reward_ratio,
        )
        reason = (
            f"optimizer applied: SL={stop_loss:.2f}%, TP={take_profit:.2f}%, "
            f"trail={trailing_stop:.2f}%, PF={optimization.profit_factor:.2f}, score={optimization.score:.2f}"
        )
        return optimized, reason

    def _score(self, total_profit: float, profit_factor: float, win_rate: float, max_drawdown: float, trades_count: int) -> float:
        if trades_count == 0:
            return -9999
        return round(total_profit + profit_factor * 20 + win_rate * 0.5 - max_drawdown * 1.2 + min(trades_count, 30), 4)

    def _is_fresh(self, optimization: StrategyOptimization) -> bool:
        if self.settings.strategy_optimizer_max_age_days <= 0 or not optimization.created_at:
            return True
        created_at = optimization.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - created_at).total_seconds() / 86400
        return age_days <= self.settings.strategy_optimizer_max_age_days

    def _positive_float(self, value: object, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    def _bounded_float(self, value: object, default: float, minimum: float, maximum: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return min(max(parsed, minimum), maximum)

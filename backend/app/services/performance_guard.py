from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Trade


@dataclass
class PerformanceGuardReport:
    allowed: bool
    reason: str
    trades_checked: int
    win_rate: float
    loss_streak: int
    total_profit: float


class PerformanceGuardService:
    async def evaluate(self, db: AsyncSession, limit: int = 20) -> PerformanceGuardReport:
        settings = get_settings()
        trades = (
            await db.execute(
                select(Trade)
                .where(Trade.exit_price.is_not(None))
                .order_by(Trade.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        if len(trades) < settings.guard_min_trades:
            return PerformanceGuardReport(True, "not enough closed trades for guard", len(trades), 0, 0, 0)

        profits = [float(trade.profit) for trade in trades]
        wins = [profit for profit in profits if profit > 0]
        win_rate = len(wins) / len(profits) * 100
        total_profit = sum(profits)
        loss_streak = self.loss_streak(profits)

        if loss_streak >= settings.guard_max_loss_streak:
            return PerformanceGuardReport(False, "loss streak limit reached", len(trades), round(win_rate, 2), loss_streak, round(total_profit, 2))
        if win_rate < settings.guard_min_win_rate:
            return PerformanceGuardReport(False, "win rate below guard threshold", len(trades), round(win_rate, 2), loss_streak, round(total_profit, 2))
        if total_profit < settings.guard_min_total_profit:
            return PerformanceGuardReport(False, "recent total profit below guard threshold", len(trades), round(win_rate, 2), loss_streak, round(total_profit, 2))
        return PerformanceGuardReport(True, "performance guard passed", len(trades), round(win_rate, 2), loss_streak, round(total_profit, 2))

    def loss_streak(self, profits: list[float]) -> int:
        streak = 0
        for profit in profits:
            if profit < 0:
                streak += 1
            else:
                break
        return streak

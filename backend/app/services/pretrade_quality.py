from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Candle
from app.services.backtesting import BacktestingService, WalkForwardReport
from app.services.risk_manager import RiskSettings


@dataclass(frozen=True)
class PreTradeQualityAssessment:
    allowed: bool
    reason: str
    candles_checked: int
    window_count: int = 0
    profitable_windows_percent: float = 0.0
    average_win_rate: float = 0.0
    average_profit_factor: float = 0.0
    total_profit: float = 0.0


class PreTradeQualityGate:
    def __init__(self, backtester: BacktestingService | None = None) -> None:
        self.settings = get_settings()
        self.backtester = backtester or BacktestingService()

    async def assess(
        self,
        db: AsyncSession,
        symbol: str,
        timeframe: str,
        risk_settings: RiskSettings,
    ) -> PreTradeQualityAssessment:
        if not self.settings.pretrade_quality_enabled:
            return PreTradeQualityAssessment(True, "pre-trade quality gate disabled", 0)

        candles = await self._recent_candles(db, symbol, timeframe, self.settings.pretrade_quality_min_candles + 240)
        used_timeframe = timeframe
        if len(candles) < self.settings.pretrade_quality_min_candles and timeframe != "1h":
            fallback_candles = await self._recent_candles(db, symbol, "1h", self.settings.pretrade_quality_min_candles + 240)
            if len(fallback_candles) > len(candles):
                candles = fallback_candles
                used_timeframe = "1h"
        if len(candles) < self.settings.pretrade_quality_min_candles:
            return PreTradeQualityAssessment(
                True,
                f"pre-trade quality warning: only {len(candles)} {used_timeframe} candles available, need {self.settings.pretrade_quality_min_candles}",
                len(candles),
            )

        train_size = max(220, min(360, len(candles) // 2))
        test_size = max(80, min(160, len(candles) // 4))
        step_size = max(60, test_size)
        report = self.backtester.walk_forward(candles, train_size=train_size, test_size=test_size, step_size=step_size)
        return self._decision(report, len(candles), risk_settings)

    async def _recent_candles(self, db: AsyncSession, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        result = await db.execute(
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    def _decision(
        self,
        report: WalkForwardReport,
        candles_checked: int,
        risk_settings: RiskSettings,
    ) -> PreTradeQualityAssessment:
        if report.window_count <= 0:
            return PreTradeQualityAssessment(True, "pre-trade quality warning: not enough walk-forward windows", candles_checked)

        total_test_trades = sum(window.test_trades_count for window in report.windows)
        profitable_windows_percent = report.profitable_windows / report.window_count * 100
        reasons: list[str] = []
        if total_test_trades < self.settings.pretrade_quality_min_trades:
            reasons.append(f"too few historical trades {total_test_trades} < {self.settings.pretrade_quality_min_trades}")
        if report.average_profit_factor < self.settings.pretrade_quality_min_profit_factor:
            reasons.append(f"profit factor {report.average_profit_factor:.2f} < {self.settings.pretrade_quality_min_profit_factor:.2f}")
        if report.average_win_rate < self.settings.pretrade_quality_min_win_rate:
            reasons.append(f"win rate {report.average_win_rate:.2f}% < {self.settings.pretrade_quality_min_win_rate:.2f}%")
        if profitable_windows_percent < self.settings.pretrade_quality_min_profitable_windows_percent:
            reasons.append(
                f"profitable windows {profitable_windows_percent:.2f}% < "
                f"{self.settings.pretrade_quality_min_profitable_windows_percent:.2f}%"
            )
        if report.total_profit <= -risk_settings.risk_percent:
            reasons.append(f"walk-forward total profit {report.total_profit:.2f} is below risk tolerance")

        allowed = not reasons
        reason = "pre-trade quality passed" if allowed else f"pre-trade quality blocked: {'; '.join(reasons)}"
        return PreTradeQualityAssessment(
            allowed=allowed,
            reason=reason,
            candles_checked=candles_checked,
            window_count=report.window_count,
            profitable_windows_percent=round(profitable_windows_percent, 2),
            average_win_rate=report.average_win_rate,
            average_profit_factor=report.average_profit_factor,
            total_profit=report.total_profit,
        )

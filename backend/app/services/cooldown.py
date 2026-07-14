from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Position, PositionStatus


@dataclass
class CooldownReport:
    allowed: bool
    reason: str


class LossCooldownGuard:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def assess(self, db: AsyncSession, symbol: str, now: datetime | None = None) -> CooldownReport:
        if not self.settings.loss_cooldown_enabled:
            return CooldownReport(True, "loss cooldown disabled")

        current_time = self._aware(now or datetime.now(timezone.utc))
        lookback_hours = max(self.settings.loss_cooldown_symbol_hours, self.settings.loss_cooldown_global_hours, 0.0)
        cutoff = current_time - timedelta(hours=lookback_hours)
        positions = (
            await db.execute(
                select(Position)
                .where(
                    Position.status == PositionStatus.CLOSED.value,
                    Position.closed_at.is_not(None),
                    Position.closed_at >= cutoff,
                )
                .order_by(Position.closed_at.desc())
                .limit(100)
            )
        ).scalars().all()
        return self.assess_positions(list(positions), symbol=symbol, now=current_time)

    def assess_positions(self, positions: list[Position], symbol: str, now: datetime | None = None) -> CooldownReport:
        if not self.settings.loss_cooldown_enabled:
            return CooldownReport(True, "loss cooldown disabled")

        current_time = self._aware(now or datetime.now(timezone.utc))
        closed = sorted(
            [position for position in positions if position.status == PositionStatus.CLOSED.value and position.closed_at],
            key=lambda item: self._aware(item.closed_at),
            reverse=True,
        )

        global_report = self._global_loss_streak_report(closed, current_time)
        if not global_report.allowed:
            return global_report

        symbol_report = self._symbol_loss_report(closed, symbol, current_time)
        if not symbol_report.allowed:
            return symbol_report

        return CooldownReport(True, "loss cooldown passed")

    def _global_loss_streak_report(self, positions: list[Position], now: datetime) -> CooldownReport:
        streak_size = max(int(self.settings.loss_cooldown_loss_streak), 0)
        if streak_size <= 0 or self.settings.loss_cooldown_global_hours <= 0:
            return CooldownReport(True, "global loss cooldown disabled")

        cutoff = now - timedelta(hours=self.settings.loss_cooldown_global_hours)
        recent = [position for position in positions if self._aware(position.closed_at) >= cutoff][:streak_size]
        if len(recent) >= streak_size and all(self._is_loss(position) for position in recent):
            symbols = ", ".join(position.symbol for position in recent)
            return CooldownReport(
                False,
                f"global loss cooldown: {streak_size} losses in a row ({symbols}), pause entries for {self.settings.loss_cooldown_global_hours:g}h",
            )
        return CooldownReport(True, "global loss cooldown passed")

    def _symbol_loss_report(self, positions: list[Position], symbol: str, now: datetime) -> CooldownReport:
        if self.settings.loss_cooldown_symbol_hours <= 0:
            return CooldownReport(True, "symbol loss cooldown disabled")

        cutoff = now - timedelta(hours=self.settings.loss_cooldown_symbol_hours)
        for position in positions:
            if position.symbol != symbol or not self._is_loss(position):
                continue
            closed_at = self._aware(position.closed_at)
            if closed_at >= cutoff:
                hours_left = max((closed_at + timedelta(hours=self.settings.loss_cooldown_symbol_hours) - now).total_seconds() / 3600, 0.0)
                return CooldownReport(
                    False,
                    f"symbol loss cooldown: {symbol} lost {float(position.pnl or 0):.2f}, wait {hours_left:.1f}h",
                )
        return CooldownReport(True, "symbol loss cooldown passed")

    def _is_loss(self, position: Position) -> bool:
        return float(position.pnl or 0.0) < -abs(self.settings.loss_cooldown_min_loss)

    def _aware(self, value: datetime | None) -> datetime:
        if value is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

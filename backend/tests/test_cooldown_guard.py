from datetime import datetime, timedelta, timezone

from app.models.entities import Position, PositionStatus
from app.services.cooldown import LossCooldownGuard


def closed_position(symbol: str, pnl: float, closed_at: datetime) -> Position:
    return Position(symbol=symbol, status=PositionStatus.CLOSED.value, pnl=pnl, closed_at=closed_at)


def guard() -> LossCooldownGuard:
    service = LossCooldownGuard()
    service.settings.loss_cooldown_enabled = True
    service.settings.loss_cooldown_symbol_hours = 6.0
    service.settings.loss_cooldown_global_hours = 3.0
    service.settings.loss_cooldown_loss_streak = 2
    service.settings.loss_cooldown_min_loss = 0.0
    return service


def test_symbol_loss_cooldown_blocks_recent_loser():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    report = guard().assess_positions(
        [closed_position("BTC/USDT", -12.0, now - timedelta(hours=2))],
        symbol="BTC/USDT",
        now=now,
    )

    assert report.allowed is False
    assert report.reason.startswith("symbol loss cooldown")


def test_symbol_loss_cooldown_ignores_old_or_profitable_position():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    service = guard()

    old_loss = service.assess_positions(
        [closed_position("BTC/USDT", -12.0, now - timedelta(hours=7))],
        symbol="BTC/USDT",
        now=now,
    )
    recent_win = service.assess_positions(
        [closed_position("BTC/USDT", 8.0, now - timedelta(hours=1))],
        symbol="BTC/USDT",
        now=now,
    )

    assert old_loss.allowed is True
    assert recent_win.allowed is True


def test_global_loss_cooldown_blocks_after_loss_streak():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    report = guard().assess_positions(
        [
            closed_position("ETH/USDT", -4.0, now - timedelta(minutes=15)),
            closed_position("SOL/USDT", -6.0, now - timedelta(minutes=40)),
            closed_position("BTC/USDT", 10.0, now - timedelta(hours=5)),
        ],
        symbol="BTC/USDT",
        now=now,
    )

    assert report.allowed is False
    assert report.reason.startswith("global loss cooldown")


def test_global_loss_cooldown_resets_after_win():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    report = guard().assess_positions(
        [
            closed_position("ETH/USDT", 3.0, now - timedelta(minutes=15)),
            closed_position("SOL/USDT", -6.0, now - timedelta(minutes=40)),
        ],
        symbol="BTC/USDT",
        now=now,
    )

    assert report.allowed is True

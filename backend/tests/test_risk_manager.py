from app.schemas.dto import StrategySignal
from app.services.risk_manager import RiskManager, RiskSettings


def settings(**overrides):
    data = {
        "balance": 1000,
        "risk_percent": 1,
        "daily_risk_percent": 3,
        "max_positions": 2,
        "min_rating": 80,
        "stop_loss_percent": 1.5,
        "take_profit_percent": 3,
        "trailing_stop_percent": 0.8,
    }
    data.update(overrides)
    return RiskSettings(**data)


def test_risk_accepts_valid_signal():
    accepted, reason = RiskManager().can_open(
        StrategySignal(symbol="BTC/USDT", signal="BUY", score=90),
        settings(),
        open_positions_count=0,
        daily_pnl=0,
    )
    assert accepted is True
    assert reason == "risk accepted"


def test_risk_blocks_daily_loss_limit():
    accepted, reason = RiskManager().can_open(
        StrategySignal(symbol="BTC/USDT", signal="BUY", score=90),
        settings(),
        open_positions_count=0,
        daily_pnl=-30,
    )
    assert accepted is False
    assert reason == "daily loss limit reached"


def test_position_size_uses_loss_budget():
    size = RiskManager().position_size(balance=1000, risk_percent=1, entry_price=100, stop_price=98)
    assert size == 5

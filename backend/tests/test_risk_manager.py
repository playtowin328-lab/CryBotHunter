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


def test_risk_blocks_oversized_trade_risk():
    accepted, reason = RiskManager().can_open(
        StrategySignal(symbol="BTC/USDT", signal="BUY", score=90),
        settings(risk_percent=3),
        open_positions_count=0,
        daily_pnl=0,
    )
    assert accepted is False
    assert reason == "risk per trade above safety limit"


def test_risk_blocks_weak_risk_reward():
    accepted, reason = RiskManager().can_open(
        StrategySignal(symbol="BTC/USDT", signal="BUY", score=90),
        settings(risk_reward_ratio=1.2),
        open_positions_count=0,
        daily_pnl=0,
    )
    assert accepted is False
    assert reason == "risk/reward ratio below safety limit"


def test_position_size_uses_loss_budget():
    size = RiskManager().position_size(balance=1000, risk_percent=1, entry_price=100, stop_price=98)
    assert size == 5


def test_exposure_percent_uses_balance_and_handles_zero_balance():
    manager = RiskManager()

    assert manager.exposure_percent(exposure=250, balance=1000) == 25
    assert manager.exposure_percent(exposure=250, balance=0) == 0


def test_exposure_guard_blocks_gross_limit():
    accepted, reason = RiskManager().can_add_exposure(
        balance=1000,
        current_gross_exposure=2900,
        current_symbol_exposure=0,
        candidate_notional=200,
        max_gross_exposure_percent=300,
        max_symbol_exposure_percent=100,
    )
    assert accepted is False
    assert reason == "gross exposure limit reached"


def test_exposure_guard_blocks_symbol_limit():
    accepted, reason = RiskManager().can_add_exposure(
        balance=1000,
        current_gross_exposure=500,
        current_symbol_exposure=950,
        candidate_notional=100,
        max_gross_exposure_percent=300,
        max_symbol_exposure_percent=100,
    )
    assert accepted is False
    assert reason == "symbol exposure limit reached"


def test_directional_exposure_reduces_risk_when_side_is_crowded():
    accepted, reason, multiplier = RiskManager().directional_exposure(
        side="LONG",
        side_counts={"LONG": 1, "SHORT": 0},
        max_same_side_positions=2,
        reduction_start=1,
        risk_multiplier=0.5,
    )

    assert accepted is True
    assert multiplier == 0.5
    assert reason == "long direction risk reduced to 0.50x"


def test_directional_exposure_blocks_when_side_limit_is_reached():
    accepted, reason, multiplier = RiskManager().directional_exposure(
        side="SHORT",
        side_counts={"LONG": 0, "SHORT": 2},
        max_same_side_positions=2,
        reduction_start=1,
        risk_multiplier=0.5,
    )

    assert accepted is False
    assert multiplier == 0.0
    assert reason == "short direction position limit reached"

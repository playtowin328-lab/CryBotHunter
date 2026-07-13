from datetime import datetime, timedelta, timezone

from app.models.entities import StrategyOptimization
from app.services.optimizer import StrategyOptimizerService
from app.services.risk_manager import RiskSettings


def test_optimizer_score_rewards_profitable_stable_reports():
    service = StrategyOptimizerService()

    strong = service._score(
        total_profit=120,
        profit_factor=2.4,
        win_rate=64,
        max_drawdown=18,
        trades_count=24,
    )
    weak = service._score(
        total_profit=-35,
        profit_factor=0.7,
        win_rate=38,
        max_drawdown=42,
        trades_count=24,
    )

    assert strong > weak


def test_optimizer_score_rejects_empty_reports():
    assert StrategyOptimizerService()._score(0, 0, 0, 0, 0) == -9999


def risk_settings():
    return RiskSettings(
        balance=1000.0,
        risk_percent=1.0,
        daily_risk_percent=3.0,
        max_positions=3,
        min_rating=80,
        stop_loss_percent=1.5,
        take_profit_percent=3.0,
        trailing_stop_percent=0.8,
    )


def optimization(**overrides):
    data = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "parameters": {
            "stop_loss_percent": 1.0,
            "take_profit_percent": 3.0,
            "trailing_stop_percent": 1.2,
        },
        "score": 88.0,
        "win_rate": 60.0,
        "profit_factor": 1.7,
        "max_drawdown": 10.0,
        "total_profit": 50.0,
        "trades_count": 8,
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return StrategyOptimization(**data)


def test_optimizer_applies_parameters_to_risk_settings():
    service = StrategyOptimizerService()

    optimized, reason = service.apply_to_risk_settings(risk_settings(), optimization())

    assert optimized.stop_loss_percent == 1.0
    assert optimized.take_profit_percent == 3.0
    assert optimized.trailing_stop_percent == 1.2
    assert optimized.risk_reward_ratio == 3.0
    assert "optimizer applied" in reason


def test_optimizer_rejects_stale_optimization(monkeypatch):
    service = StrategyOptimizerService()
    monkeypatch.setattr(service.settings, "strategy_optimizer_max_age_days", 14)
    stale = optimization(created_at=datetime.now(timezone.utc) - timedelta(days=30))

    assert service._is_fresh(stale) is False

from app.services.optimizer import StrategyOptimizerService


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

from datetime import datetime, timedelta, timezone

from app.schemas.dto import MarketCoin
from app.services.learning import LearningService


def coin(**overrides):
    data = {
        "symbol": "BTC/USDT",
        "price": 100,
        "volume_24h": 2_000_000_000,
        "price_change_percent": 4,
        "atr": 2,
        "rsi": 62,
        "ema20": 106,
        "ema50": 100,
        "ema200": 90,
        "macd": 10,
        "funding_rate": 0.01,
        "open_interest": 1_500_000_000,
        "rating": 88,
        "regime": "TRENDING_UP",
        "regime_score": 82,
        "regime_reason": "trend confirmed",
    }
    data.update(overrides)
    return MarketCoin(**data)


def test_learning_entry_context_buckets_market_features():
    context = LearningService().entry_context(coin(), "BUY", ["ok"])

    assert context["side"] == "LONG"
    assert context["rsi_bucket"] == "bullish"
    assert context["atr_bucket"] == "normal"
    assert context["trend_stack"] == "bullish"
    assert context["rating_bucket"] == "elite"


def test_learning_penalty_delta_penalizes_losses_and_forgives_wins():
    service = LearningService()

    assert service._penalty_delta(-10) > 0
    assert service._penalty_delta(10) < 0


def test_learning_service_has_bounded_penalty_policy():
    service = LearningService()

    assert service.max_penalty == 5.0
    assert service.block_threshold > service.warn_threshold


def test_learning_confidence_requires_multiple_observations():
    service = LearningService()

    assert service.rule_confidence(0) == 0
    assert service.rule_confidence(1) == 0.5
    assert service.rule_confidence(2) == 1.0


def test_learning_risk_level_uses_effective_penalty():
    service = LearningService()

    assert service.risk_level(3.0, 1) == "WARN"
    assert service.risk_level(3.0, 2) == "BLOCK"


def test_learning_confidence_decays_with_age():
    service = LearningService()
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=service.half_life_days)

    assert 0.49 <= service.recency_weight(old_timestamp) <= 0.51
    assert 0.49 <= service.rule_confidence(2, old_timestamp) <= 0.51

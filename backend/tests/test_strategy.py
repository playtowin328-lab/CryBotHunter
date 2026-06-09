from app.schemas.dto import MarketCoin
from app.services.strategy import StrategyCore


def coin(**overrides):
    data = {
        "symbol": "BTC/USDT",
        "price": 110,
        "volume_24h": 2_000_000_000,
        "price_change_percent": 4,
        "atr": 3,
        "rsi": 62,
        "ema20": 105,
        "ema50": 100,
        "ema200": 90,
        "macd": 10,
        "funding_rate": 0.01,
        "open_interest": 1_500_000_000,
        "rating": 88,
    }
    data.update(overrides)
    return MarketCoin(**data)


def test_strategy_returns_buy_when_long_rules_match():
    signal = StrategyCore().evaluate(coin())
    assert signal.signal == "BUY"
    assert signal.score >= 88


def test_strategy_returns_sell_when_short_rules_match():
    signal = StrategyCore().evaluate(coin(price=80, rsi=35, ema50=90, ema200=110, rating=90))
    assert signal.signal == "SELL"
    assert signal.score >= 90


def test_strategy_waits_when_rating_is_low():
    signal = StrategyCore().evaluate(coin(rating=40))
    assert signal.signal == "WAIT"

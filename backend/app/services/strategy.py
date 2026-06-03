from app.schemas.dto import MarketCoin, StrategySignal


class StrategyCore:
    def evaluate(self, coin: MarketCoin, average_volume: float | None = None) -> StrategySignal:
        average_volume = average_volume or coin.volume_24h * 0.75
        reasons: list[str] = []

        long_rules = [
            (coin.ema50 > coin.ema200, "EMA50 above EMA200"),
            (55 <= coin.rsi <= 75, "RSI in long range"),
            (coin.price > coin.ema50, "price above EMA50"),
            (coin.volume_24h > average_volume, "volume above average"),
            (coin.rating > 80, "rating above 80"),
        ]
        short_rules = [
            (coin.ema50 < coin.ema200, "EMA50 below EMA200"),
            (25 <= coin.rsi <= 45, "RSI in short range"),
            (coin.price < coin.ema50, "price below EMA50"),
            (coin.volume_24h > average_volume, "volume above average"),
            (coin.rating > 80, "rating above 80"),
        ]

        long_score = self._score(long_rules, coin.rating)
        short_score = self._score(short_rules, coin.rating)

        if all(ok for ok, _ in long_rules):
            reasons = [text for ok, text in long_rules if ok]
            return StrategySignal(symbol=coin.symbol, signal="BUY", score=max(coin.rating, long_score), reasons=reasons)
        if all(ok for ok, _ in short_rules):
            reasons = [text for ok, text in short_rules if ok]
            return StrategySignal(symbol=coin.symbol, signal="SELL", score=max(coin.rating, short_score), reasons=reasons)
        return StrategySignal(symbol=coin.symbol, signal="WAIT", score=max(long_score, short_score), reasons=reasons)

    def _score(self, rules: list[tuple[bool, str]], rating: int) -> int:
        matched = sum(1 for ok, _ in rules if ok)
        return int(round((matched / len(rules)) * 70 + (rating / 100) * 30))

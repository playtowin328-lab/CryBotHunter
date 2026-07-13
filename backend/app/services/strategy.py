from app.schemas.dto import MarketCoin, StrategySignal


class StrategyCore:
    def evaluate(self, coin: MarketCoin, average_volume: float | None = None) -> StrategySignal:
        average_volume = average_volume or coin.volume_24h * 0.75
        wait_reasons: list[str] = []
        long_regime = coin.regime in {"TRENDING_UP", "UNKNOWN"}
        short_regime = coin.regime in {"TRENDING_DOWN", "UNKNOWN"}
        if coin.regime in {"LOW_LIQUIDITY", "HIGH_VOLATILITY"}:
            return StrategySignal(
                symbol=coin.symbol,
                signal="WAIT",
                score=min(coin.rating, coin.regime_score),
                reasons=[f"blocked by market regime: {coin.regime}"],
            )
        if coin.regime != "UNKNOWN" and coin.regime_score < 45:
            return StrategySignal(
                symbol=coin.symbol,
                signal="WAIT",
                score=min(coin.rating, coin.regime_score),
                reasons=[f"market regime score too weak: {coin.regime_score}"],
            )

        atr_percent = coin.atr / coin.price * 100 if coin.price > 0 else 0
        if atr_percent < 0.25:
            return StrategySignal(
                symbol=coin.symbol,
                signal="WAIT",
                score=min(coin.rating, 55),
                reasons=[f"volatility too low for clean risk/reward: ATR {atr_percent:.2f}%"],
            )
        if atr_percent > 7.5:
            return StrategySignal(
                symbol=coin.symbol,
                signal="WAIT",
                score=min(coin.rating, 55),
                reasons=[f"volatility too high for safe entry: ATR {atr_percent:.2f}%"],
            )

        long_rules = [
            (long_regime, "market regime supports long"),
            (coin.ema20 > coin.ema50 > coin.ema200, "EMA20/50/200 bullish alignment"),
            (50 <= coin.rsi <= 68, "RSI in long range without overextension"),
            (coin.price > coin.ema20, "price above EMA20"),
            (coin.macd > 0, "MACD positive"),
            (coin.volume_24h > average_volume, "volume above average"),
            (coin.rating > 80, "rating above 80"),
        ]
        short_rules = [
            (short_regime, "market regime supports short"),
            (coin.ema20 < coin.ema50 < coin.ema200, "EMA20/50/200 bearish alignment"),
            (32 <= coin.rsi <= 50, "RSI in short range without overextension"),
            (coin.price < coin.ema20, "price below EMA20"),
            (coin.macd < 0, "MACD negative"),
            (coin.volume_24h > average_volume, "volume above average"),
            (coin.rating > 80, "rating above 80"),
        ]

        long_score = self._score(long_rules, coin.rating)
        short_score = self._score(short_rules, coin.rating)

        if all(ok for ok, _ in long_rules):
            reasons = [text for ok, text in long_rules if ok]
            reasons.append(f"ATR risk is tradable: {atr_percent:.2f}%")
            return StrategySignal(symbol=coin.symbol, signal="BUY", score=max(coin.rating, long_score), reasons=reasons)
        if all(ok for ok, _ in short_rules):
            reasons = [text for ok, text in short_rules if ok]
            reasons.append(f"ATR risk is tradable: {atr_percent:.2f}%")
            return StrategySignal(symbol=coin.symbol, signal="SELL", score=max(coin.rating, short_score), reasons=reasons)
        if long_score >= short_score:
            wait_reasons = [f"long missing: {text}" for ok, text in long_rules if not ok]
        else:
            wait_reasons = [f"short missing: {text}" for ok, text in short_rules if not ok]
        return StrategySignal(symbol=coin.symbol, signal="WAIT", score=max(long_score, short_score), reasons=wait_reasons)

    def _score(self, rules: list[tuple[bool, str]], rating: int) -> int:
        matched = sum(1 for ok, _ in rules if ok)
        return int(round((matched / len(rules)) * 70 + (rating / 100) * 30))

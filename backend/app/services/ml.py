from app.schemas.dto import MarketCoin, MlPrediction


class MlSignalService:
    def predict(self, coin: MarketCoin) -> MlPrediction:
        trend_bias = 20 if coin.ema50 > coin.ema200 else -20
        rsi_bias = max(min((coin.rsi - 50) * 1.2, 20), -20)
        rating_bias = (coin.rating - 50) * 0.4
        long_probability = int(max(1, min(99, 50 + trend_bias + rsi_bias + rating_bias)))
        return MlPrediction(
            symbol=coin.symbol,
            long_probability=long_probability,
            short_probability=100 - long_probability,
        )

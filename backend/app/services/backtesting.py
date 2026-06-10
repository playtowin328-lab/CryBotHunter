from dataclasses import dataclass

import pandas as pd

from app.models.entities import Candle
from app.schemas.dto import MarketCoin
from app.services.market_scanner import MarketScanner
from app.services.strategy import StrategyCore


@dataclass
class BacktestReport:
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    average_profit: float
    average_loss: float
    trades_count: int = 0
    total_profit: float = 0.0


class BacktestingService:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.strategy = StrategyCore()

    def run(
        self,
        candles: list[Candle],
        risk_per_trade: float = 10.0,
        stop_loss_percent: float = 1.5,
        take_profit_percent: float = 3.0,
        trailing_stop_percent: float = 0.0,
    ) -> BacktestReport:
        if len(candles) < 220:
            return self.summarize([])
        frame = pd.DataFrame(
            [
                {
                    "open": item.open,
                    "high": item.high,
                    "low": item.low,
                    "close": item.close,
                    "volume": item.volume,
                }
                for item in candles
            ]
        )
        frame = self.scanner.calculate_indicators(frame).dropna().reset_index(drop=True)
        profits: list[float] = []
        position: dict | None = None
        for _, row in frame.iterrows():
            if position:
                exit_price = None
                if position["side"] == "LONG":
                    if trailing_stop_percent > 0:
                        trailed_stop = float(row["close"]) * (1 - trailing_stop_percent / 100)
                        position["stop"] = max(position["stop"], trailed_stop)
                    if row["low"] <= position["stop"]:
                        exit_price = position["stop"]
                    elif row["high"] >= position["take"]:
                        exit_price = position["take"]
                    if exit_price is not None:
                        profits.append((exit_price - position["entry"]) * position["volume"])
                        position = None
                else:
                    if trailing_stop_percent > 0:
                        trailed_stop = float(row["close"]) * (1 + trailing_stop_percent / 100)
                        position["stop"] = min(position["stop"], trailed_stop)
                    if row["high"] >= position["stop"]:
                        exit_price = position["stop"]
                    elif row["low"] <= position["take"]:
                        exit_price = position["take"]
                    if exit_price is not None:
                        profits.append((position["entry"] - exit_price) * position["volume"])
                        position = None
                if position:
                    continue

            average_volume = float(frame["volume"].rolling(20).mean().iloc[int(row.name)] or row["volume"])
            coin = MarketCoin(
                symbol=candles[0].symbol,
                price=float(row["close"]),
                volume_24h=float(row["volume"]),
                price_change_percent=0,
                atr=float(row["atr"]),
                rsi=float(row["rsi"]),
                ema20=float(row["ema20"]),
                ema50=float(row["ema50"]),
                ema200=float(row["ema200"]),
                macd=float(row["macd"]),
                funding_rate=0,
                open_interest=1_000_000_000,
                rating=85,
            )
            signal = self.strategy.evaluate(coin, average_volume=average_volume)
            if signal.signal in {"BUY", "SELL"}:
                entry = float(row["close"])
                stop = entry * (1 - stop_loss_percent / 100) if signal.signal == "BUY" else entry * (1 + stop_loss_percent / 100)
                take = entry * (1 + take_profit_percent / 100) if signal.signal == "BUY" else entry * (1 - take_profit_percent / 100)
                volume = risk_per_trade / abs(entry - stop)
                position = {"side": "LONG" if signal.signal == "BUY" else "SHORT", "entry": entry, "stop": stop, "take": take, "volume": volume}
        return self.summarize(profits)

    def summarize(self, profits: list[float]) -> BacktestReport:
        wins = [value for value in profits if value > 0]
        losses = [abs(value) for value in profits if value < 0]
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        win_rate = len(wins) / len(profits) * 100 if profits else 0
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for profit in profits:
            equity += profit
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return BacktestReport(
            win_rate=round(win_rate, 2),
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss else 0,
            sharpe_ratio=0.0,
            max_drawdown=round(max_drawdown, 2),
            average_profit=round(gross_profit / len(wins), 2) if wins else 0,
            average_loss=round(gross_loss / len(losses), 2) if losses else 0,
            trades_count=len(profits),
            total_profit=round(sum(profits), 2),
        )

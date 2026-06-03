from dataclasses import dataclass


@dataclass
class BacktestReport:
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    average_profit: float
    average_loss: float


class BacktestingService:
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
        )

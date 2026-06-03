from dataclasses import dataclass

from app.schemas.dto import StrategySignal


@dataclass
class RiskSettings:
    balance: float
    risk_percent: float
    daily_risk_percent: float
    max_positions: int
    min_rating: int
    stop_loss_percent: float
    take_profit_percent: float


class RiskManager:
    def can_open(
        self,
        signal: StrategySignal,
        settings: RiskSettings,
        open_positions_count: int,
        daily_pnl: float,
    ) -> tuple[bool, str]:
        if signal.signal == "WAIT":
            return False, "strategy returned WAIT"
        if open_positions_count >= settings.max_positions:
            return False, "maximum open positions reached"
        if signal.score < settings.min_rating:
            return False, "signal score below minimum rating"
        daily_loss_limit = -settings.balance * settings.daily_risk_percent / 100
        if daily_pnl <= daily_loss_limit:
            return False, "daily loss limit reached"
        return True, "risk accepted"

    def position_size(self, balance: float, risk_percent: float, entry_price: float, stop_price: float) -> float:
        loss_budget = balance * risk_percent / 100
        price_risk = abs(entry_price - stop_price)
        if price_risk <= 0:
            return 0
        return round(loss_budget / price_risk, 6)

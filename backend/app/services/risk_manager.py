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
    trailing_stop_percent: float
    atr_stop_multiplier: float = 1.5
    risk_reward_ratio: float = 2.0
    breakeven_trigger_r: float = 1.0
    breakeven_offset_percent: float = 0.05
    partial_take_profit_r: float = 1.0
    partial_close_percent: float = 50.0
    max_risk_percent_per_trade: float = 2.0
    min_risk_reward_ratio: float = 1.5


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
        if settings.risk_percent > settings.max_risk_percent_per_trade:
            return False, "risk per trade above safety limit"
        if settings.risk_reward_ratio < settings.min_risk_reward_ratio:
            return False, "risk/reward ratio below safety limit"
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

    def position_notional(self, price: float, volume: float) -> float:
        return round(abs(price * volume), 4)

    def can_add_exposure(
        self,
        balance: float,
        current_gross_exposure: float,
        current_symbol_exposure: float,
        candidate_notional: float,
        max_gross_exposure_percent: float,
        max_symbol_exposure_percent: float,
    ) -> tuple[bool, str]:
        if balance <= 0:
            return False, "balance is zero"
        gross_limit = balance * max_gross_exposure_percent / 100
        symbol_limit = balance * max_symbol_exposure_percent / 100
        if current_gross_exposure + candidate_notional > gross_limit:
            return False, "gross exposure limit reached"
        if current_symbol_exposure + candidate_notional > symbol_limit:
            return False, "symbol exposure limit reached"
        return True, "exposure accepted"

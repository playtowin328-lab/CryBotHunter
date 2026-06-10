from app.models.entities import Position
from app.schemas.dto import AgentAnalysisOut, AgentDecisionOut, MarketCoin
from app.services.risk_manager import RiskSettings
from app.services.trading_engine import TradingEngine


def analysis(action: str, approved: bool = True, consensus_score: float = 0.8) -> AgentAnalysisOut:
    decision = AgentDecisionOut(
        agent_name="TradeCommittee",
        symbol="BTC/USDT",
        action=action,
        confidence=0.8,
        rationale="test",
    )


def coin() -> MarketCoin:
    return MarketCoin(
        symbol="BTC/USDT",
        price=100,
        volume_24h=1_000_000_000,
        price_change_percent=2,
        atr=2,
        rsi=62,
        ema20=105,
        ema50=100,
        ema200=90,
        macd=1,
        funding_rate=0.01,
        open_interest=1_000_000_000,
        rating=90,
    )


def risk_settings() -> RiskSettings:
    return RiskSettings(
        balance=1000,
        risk_percent=1,
        daily_risk_percent=3,
        max_positions=3,
        min_rating=80,
        stop_loss_percent=1,
        take_profit_percent=3,
        trailing_stop_percent=0.8,
    )
    risk = AgentDecisionOut(
        agent_name="RiskSupervisorAgent",
        symbol="BTC/USDT",
        action="ALLOW" if approved else "BLOCK",
        confidence=0.8,
        rationale="test",
    )
    return AgentAnalysisOut(
        symbol="BTC/USDT",
        market=decision,
        risk=risk,
        committee=[],
        consensus_score=consensus_score,
        final_action=action,
        final_confidence=0.8,
        approved=approved,
    )


def test_long_position_pnl_and_take_profit_exit():
    position = Position(
        symbol="BTC/USDT",
        side="LONG",
        entry_price=100,
        current_price=106,
        volume=2,
        stop=98,
        take=105,
        trailing_stop_percent=0.8,
        highest_price=106,
        lowest_price=100,
    )
    engine = TradingEngine()
    assert engine._pnl(position, 106) == 12
    assert engine._exit_reason(position) == "TAKE_PROFIT"


def test_short_position_pnl_and_stop_loss_exit():
    position = Position(
        symbol="ETH/USDT",
        side="SHORT",
        entry_price=100,
        current_price=103,
        volume=3,
        stop=102,
        take=95,
        trailing_stop_percent=0.8,
        highest_price=103,
        lowest_price=99,
    )
    engine = TradingEngine()
    assert engine._pnl(position, 103) == -9
    assert engine._exit_reason(position) == "STOP_LOSS"


def test_trailing_stop_moves_only_in_favorable_direction():
    position = Position(
        symbol="SOL/USDT",
        side="LONG",
        entry_price=100,
        current_price=110,
        volume=1,
        stop=98,
        take=120,
        trailing_stop_percent=2,
        highest_price=110,
        lowest_price=100,
    )
    TradingEngine()._apply_trailing_stop(position)
    assert position.stop == 107.8


def test_committee_gate_allows_matching_high_consensus_signal():
    assert TradingEngine()._committee_allows_signal(analysis("BUY"), "BUY")


def test_committee_gate_rejects_mismatch_or_low_consensus():
    engine = TradingEngine()
    assert not engine._committee_allows_signal(analysis("SELL"), "BUY")
    assert not engine._committee_allows_signal(analysis("BUY", consensus_score=0.4), "BUY")


def test_exposure_gate_rejects_overloaded_portfolio():
    engine = TradingEngine()
    accepted, reason, candidate = engine._exposure_gate(
        coin(),
        "BUY",
        balance=1000,
        settings=risk_settings(),
        exposure={"gross": 2950, "symbols": {}},
    )
    assert accepted is False
    assert reason == "gross exposure limit reached"
    assert candidate > 0

import pytest

from app.schemas.dto import AgentDecisionOut, MarketCoin
from app.services.agents import AgentOrchestrator, LiquidityAgent, MarketAnalystAgent, RegimeAgent, RiskSupervisorAgent, TrendAgent, VolatilityAgent


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
        "regime": "TRENDING_UP",
        "regime_score": 82,
        "regime_reason": "test trend",
    }
    data.update(overrides)
    return MarketCoin(**data)


def test_market_agent_returns_structured_decision():
    decision = MarketAnalystAgent().decide(coin())
    assert decision.agent_name == "MarketAnalystAgent"
    assert decision.symbol == "BTC/USDT"
    assert decision.action in {"BUY", "SELL", "WAIT"}
    assert 0 <= decision.confidence <= 1


@pytest.mark.asyncio
async def test_risk_agent_blocks_low_confidence(monkeypatch):
    class Result:
        def scalar_one(self):
            return 0

    class Db:
        async def execute(self, *_args, **_kwargs):
            return Result()

    market = AgentDecisionOut(
        agent_name="MarketAnalystAgent",
        symbol="BTC/USDT",
        action="BUY",
        confidence=0.4,
        rationale="low confidence",
    )
    decision = await RiskSupervisorAgent().decide(Db(), market)
    assert decision.action == "BLOCK"


def test_orchestrator_forces_wait_on_agent_disagreement():
    market = AgentDecisionOut(
        agent_name="MarketAnalystAgent",
        symbol="BTC/USDT",
        action="BUY",
        confidence=0.9,
        rationale="local buy",
    )
    llm = AgentDecisionOut(
        agent_name="LlmAdvisorAgent",
        symbol="BTC/USDT",
        action="SELL",
        confidence=0.9,
        rationale="llm sell",
    )
    combined = AgentOrchestrator()._combine(market, llm)
    assert combined.action == "WAIT"
    assert combined.confidence <= 0.55


def test_trade_committee_approves_strong_consensus():
    market = AgentDecisionOut(
        agent_name="MarketAnalystAgent",
        symbol="BTC/USDT",
        action="BUY",
        confidence=0.88,
        rationale="local buy",
    )
    committee = [
        RegimeAgent().decide(coin()),
        TrendAgent().decide(coin()),
        AgentDecisionOut(agent_name="MomentumAgent", symbol="BTC/USDT", action="BUY", confidence=0.8, rationale="momentum buy"),
        LiquidityAgent().decide(coin()),
        VolatilityAgent().decide(coin()),
    ]

    decision, consensus = AgentOrchestrator()._committee_consensus(market, None, committee)

    assert decision.action == "BUY"
    assert consensus >= 0.66


def test_regime_agent_blocks_bad_regime():
    decision = RegimeAgent().decide(coin(regime="HIGH_VOLATILITY", regime_score=25, regime_reason="too hot"))
    assert decision.action == "BLOCK"
    assert decision.confidence >= 0.9


def test_trade_committee_veto_blocks_thin_liquidity():
    market = AgentDecisionOut(
        agent_name="MarketAnalystAgent",
        symbol="BTC/USDT",
        action="BUY",
        confidence=0.88,
        rationale="local buy",
    )
    committee = [
        TrendAgent().decide(coin()),
        LiquidityAgent().decide(coin(volume_24h=10_000, open_interest=10_000)),
        VolatilityAgent().decide(coin()),
    ]

    decision, consensus = AgentOrchestrator()._committee_consensus(market, None, committee)

    assert decision.action == "WAIT"
    assert consensus == 0

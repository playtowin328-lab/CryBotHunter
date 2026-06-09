import pytest

from app.schemas.dto import AgentDecisionOut, MarketCoin
from app.services.agents import AgentOrchestrator, MarketAnalystAgent, RiskSupervisorAgent


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

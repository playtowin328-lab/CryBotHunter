from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AgentDecision, Position
from app.schemas.dto import AgentAnalysisOut, AgentDecisionOut, MarketCoin
from app.services.llm import LlmAdvisorProvider
from app.services.market_scanner import MarketScanner
from app.services.ml import MlSignalService
from app.services.strategy import StrategyCore


class MarketAnalystAgent:
    name = "MarketAnalystAgent"

    def decide(self, coin: MarketCoin) -> AgentDecisionOut:
        signal = StrategyCore().evaluate(coin)
        ml = MlSignalService().predict(coin)
        trend = "bullish" if coin.ema50 > coin.ema200 else "bearish"
        confidence = min(0.99, max(signal.score / 100, max(ml.long_probability, ml.short_probability) / 100))
        action = signal.signal
        rationale = (
            f"{trend} structure, rating={coin.rating}, RSI={coin.rsi:.2f}, "
            f"ML long={ml.long_probability}%, short={ml.short_probability}%."
        )
        if action == "WAIT":
            confidence = min(confidence, 0.65)
        return AgentDecisionOut(
            agent_name=self.name,
            symbol=coin.symbol,
            action=action,
            confidence=round(confidence, 2),
            rationale=rationale,
            context={
                "rating": coin.rating,
                "rsi": round(coin.rsi, 2),
                "ema50": round(coin.ema50, 4),
                "ema200": round(coin.ema200, 4),
                "long_probability": ml.long_probability,
                "short_probability": ml.short_probability,
            },
        )


class RiskSupervisorAgent:
    name = "RiskSupervisorAgent"

    async def decide(self, db: AsyncSession, market_decision: AgentDecisionOut, min_confidence: float = 0.72) -> AgentDecisionOut:
        open_positions = (
            await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
        ).scalar_one()
        duplicate = (
            await db.execute(
                select(func.count()).select_from(Position).where(
                    Position.status == "OPEN",
                    Position.symbol == market_decision.symbol,
                )
            )
        ).scalar_one()

        action = "ALLOW"
        rationale = "Risk checks passed."
        confidence = market_decision.confidence
        if market_decision.action == "WAIT":
            action = "BLOCK"
            rationale = "Market agent is waiting."
        elif market_decision.confidence < min_confidence:
            action = "BLOCK"
            rationale = f"Confidence {market_decision.confidence:.2f} below threshold {min_confidence:.2f}."
        elif duplicate:
            action = "BLOCK"
            rationale = "Position already open for symbol."
        elif open_positions >= 5:
            action = "REDUCE_SIZE"
            rationale = "Portfolio already has high number of open positions."
            confidence = min(confidence, 0.6)

        return AgentDecisionOut(
            agent_name=self.name,
            symbol=market_decision.symbol,
            action=action,
            confidence=round(confidence, 2),
            rationale=rationale,
            context={"open_positions": int(open_positions), "duplicate_positions": int(duplicate)},
        )


class LlmAdvisorAgent:
    name = "LlmAdvisorAgent"

    def __init__(self) -> None:
        self.provider = LlmAdvisorProvider()

    async def decide(self, coin: MarketCoin, market_decision: AgentDecisionOut) -> AgentDecisionOut | None:
        advice = await self.provider.advise(coin, market_decision.context)
        if not advice:
            return None
        action = advice.action
        confidence = advice.confidence
        rationale = advice.rationale
        if market_decision.action in {"BUY", "SELL"} and action not in {market_decision.action, "WAIT"}:
            action = "WAIT"
            confidence = min(confidence, 0.55)
            rationale = f"LLM disagreed with local signal; forcing WAIT. Original rationale: {advice.rationale}"
        return AgentDecisionOut(
            agent_name=self.name,
            symbol=coin.symbol,
            action=action,
            confidence=round(confidence, 2),
            rationale=rationale,
            context={"invalid_if": advice.invalid_if, "provider": "openai"},
        )


class AgentOrchestrator:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.market_agent = MarketAnalystAgent()
        self.llm_agent = LlmAdvisorAgent()
        self.risk_agent = RiskSupervisorAgent()

    async def analyze(self, db: AsyncSession, symbol: str) -> AgentAnalysisOut:
        coins = await self.scanner.scan([symbol])
        coin = coins[0]
        market = self.market_agent.decide(coin)
        llm = await self.llm_agent.decide(coin, market)
        candidate = self._combine(market, llm)
        risk = await self.risk_agent.decide(db, candidate)
        approved = candidate.action in {"BUY", "SELL"} and risk.action in {"ALLOW", "REDUCE_SIZE"}
        final_action = candidate.action if approved else "BLOCK" if risk.action == "BLOCK" else "WAIT"
        final_confidence = min(candidate.confidence, risk.confidence)
        await self._persist(db, market)
        if llm:
            await self._persist(db, llm)
        await self._persist(db, risk)
        await db.commit()
        return AgentAnalysisOut(
            symbol=symbol,
            market=market,
            llm=llm,
            risk=risk,
            final_action=final_action,
            final_confidence=round(final_confidence, 2),
            approved=approved,
        )

    def _combine(self, market: AgentDecisionOut, llm: AgentDecisionOut | None) -> AgentDecisionOut:
        if not llm:
            return market
        if llm.action == "WAIT":
            return AgentDecisionOut(
                agent_name="AgentOrchestrator",
                symbol=market.symbol,
                action="WAIT",
                confidence=min(market.confidence, llm.confidence),
                rationale="LLM advisor requested WAIT.",
                context={"market_action": market.action, "llm_action": llm.action},
            )
        if market.action == llm.action:
            return AgentDecisionOut(
                agent_name="AgentOrchestrator",
                symbol=market.symbol,
                action=market.action,
                confidence=min(0.99, (market.confidence + llm.confidence) / 2),
                rationale="Market and LLM agents agree.",
                context={"market_confidence": market.confidence, "llm_confidence": llm.confidence},
            )
        return AgentDecisionOut(
            agent_name="AgentOrchestrator",
            symbol=market.symbol,
            action="WAIT",
            confidence=min(market.confidence, llm.confidence, 0.55),
            rationale="Agent disagreement; forcing WAIT.",
            context={"market_action": market.action, "llm_action": llm.action},
        )

    async def _persist(self, db: AsyncSession, decision: AgentDecisionOut) -> None:
        db.add(
            AgentDecision(
                agent_name=decision.agent_name,
                symbol=decision.symbol,
                action=decision.action,
                confidence=decision.confidence,
                rationale=decision.rationale,
                context=decision.context,
            )
        )

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AgentDecision, Position
from app.schemas.dto import AgentAnalysisOut, AgentDecisionOut, MarketCoin
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


class AgentOrchestrator:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.market_agent = MarketAnalystAgent()
        self.risk_agent = RiskSupervisorAgent()

    async def analyze(self, db: AsyncSession, symbol: str) -> AgentAnalysisOut:
        coins = await self.scanner.scan([symbol])
        coin = coins[0]
        market = self.market_agent.decide(coin)
        risk = await self.risk_agent.decide(db, market)
        approved = market.action in {"BUY", "SELL"} and risk.action in {"ALLOW", "REDUCE_SIZE"}
        final_action = market.action if approved else "BLOCK" if risk.action == "BLOCK" else "WAIT"
        final_confidence = min(market.confidence, risk.confidence)
        await self._persist(db, market)
        await self._persist(db, risk)
        await db.commit()
        return AgentAnalysisOut(
            symbol=symbol,
            market=market,
            risk=risk,
            final_action=final_action,
            final_confidence=round(final_confidence, 2),
            approved=approved,
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

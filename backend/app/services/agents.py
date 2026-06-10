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


class TrendAgent:
    name = "TrendAgent"

    def decide(self, coin: MarketCoin) -> AgentDecisionOut:
        bullish = coin.ema20 > coin.ema50 > coin.ema200 and coin.price > coin.ema50
        bearish = coin.ema20 < coin.ema50 < coin.ema200 and coin.price < coin.ema50
        spread = abs(coin.ema50 - coin.ema200) / max(coin.price, 1)
        confidence = min(0.95, 0.55 + spread * 8 + max(coin.rating - 70, 0) / 100)
        action = "BUY" if bullish else "SELL" if bearish else "WAIT"
        rationale = (
            f"EMA stack action={action}; price={coin.price:.4f}, "
            f"EMA50={coin.ema50:.4f}, EMA200={coin.ema200:.4f}."
        )
        if action == "WAIT":
            confidence = 0.52
        return AgentDecisionOut(
            agent_name=self.name,
            symbol=coin.symbol,
            action=action,
            confidence=round(confidence, 2),
            rationale=rationale,
            context={"ema20": coin.ema20, "ema50": coin.ema50, "ema200": coin.ema200, "rating": coin.rating},
        )


class MomentumAgent:
    name = "MomentumAgent"

    def decide(self, coin: MarketCoin) -> AgentDecisionOut:
        long_zone = 55 <= coin.rsi <= 75 and coin.macd > 0
        short_zone = 25 <= coin.rsi <= 45 and coin.macd < 0
        action = "BUY" if long_zone else "SELL" if short_zone else "WAIT"
        confidence = 0.7
        if action == "BUY":
            confidence += min((coin.rsi - 55) / 100, 0.15)
        elif action == "SELL":
            confidence += min((45 - coin.rsi) / 100, 0.15)
        else:
            confidence = 0.5
        return AgentDecisionOut(
            agent_name=self.name,
            symbol=coin.symbol,
            action=action,
            confidence=round(min(confidence, 0.9), 2),
            rationale=f"RSI={coin.rsi:.2f}, MACD={coin.macd:.4f}; momentum action={action}.",
            context={"rsi": round(coin.rsi, 2), "macd": round(coin.macd, 4)},
        )


class LiquidityAgent:
    name = "LiquidityAgent"

    def decide(self, coin: MarketCoin) -> AgentDecisionOut:
        liquid = coin.volume_24h >= 100_000_000 and coin.open_interest >= 100_000_000
        action = "ALLOW" if liquid else "BLOCK"
        confidence = 0.9 if liquid else 0.8
        rationale = (
            f"Volume 24h={coin.volume_24h:.0f}, open interest={coin.open_interest:.0f}; "
            f"liquidity {'accepted' if liquid else 'too thin'}."
        )
        return AgentDecisionOut(
            agent_name=self.name,
            symbol=coin.symbol,
            action=action,
            confidence=confidence,
            rationale=rationale,
            context={"volume_24h": coin.volume_24h, "open_interest": coin.open_interest},
        )


class VolatilityAgent:
    name = "VolatilityAgent"

    def decide(self, coin: MarketCoin) -> AgentDecisionOut:
        atr_percent = coin.atr / max(coin.price, 1) * 100
        funding_risk = abs(coin.funding_rate) > 0.08
        too_hot = atr_percent > 8 or funding_risk
        action = "BLOCK" if too_hot else "ALLOW"
        confidence = 0.85 if too_hot else 0.75
        rationale = f"ATR={atr_percent:.2f}% of price, funding={coin.funding_rate:.4f}; volatility action={action}."
        return AgentDecisionOut(
            agent_name=self.name,
            symbol=coin.symbol,
            action=action,
            confidence=confidence,
            rationale=rationale,
            context={"atr_percent": round(atr_percent, 2), "funding_rate": coin.funding_rate},
        )


class AgentOrchestrator:
    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.market_agent = MarketAnalystAgent()
        self.llm_agent = LlmAdvisorAgent()
        self.risk_agent = RiskSupervisorAgent()
        self.committee_agents = [TrendAgent(), MomentumAgent(), LiquidityAgent(), VolatilityAgent()]

    async def analyze(self, db: AsyncSession, symbol: str) -> AgentAnalysisOut:
        coins = await self.scanner.scan([symbol])
        coin = coins[0]
        market = self.market_agent.decide(coin)
        llm = await self.llm_agent.decide(coin, market)
        committee = [agent.decide(coin) for agent in self.committee_agents]
        candidate, consensus_score = self._committee_consensus(market, llm, committee)
        risk = await self.risk_agent.decide(db, candidate)
        approved = candidate.action in {"BUY", "SELL"} and risk.action in {"ALLOW", "REDUCE_SIZE"}
        final_action = candidate.action if approved else "BLOCK" if risk.action == "BLOCK" else "WAIT"
        final_confidence = min(candidate.confidence, risk.confidence)
        await self._persist(db, market)
        if llm:
            await self._persist(db, llm)
        for decision in committee:
            await self._persist(db, decision)
        await self._persist(db, candidate)
        await self._persist(db, risk)
        await db.commit()
        return AgentAnalysisOut(
            symbol=symbol,
            market=market,
            llm=llm,
            risk=risk,
            committee=committee,
            consensus_score=round(consensus_score, 2),
            final_action=final_action,
            final_confidence=round(final_confidence, 2),
            approved=approved,
        )

    def _committee_consensus(
        self,
        market: AgentDecisionOut,
        llm: AgentDecisionOut | None,
        committee: list[AgentDecisionOut],
    ) -> tuple[AgentDecisionOut, float]:
        if any(decision.action == "BLOCK" for decision in committee):
            blockers = [decision.agent_name for decision in committee if decision.action == "BLOCK"]
            return (
                AgentDecisionOut(
                    agent_name="TradeCommittee",
                    symbol=market.symbol,
                    action="WAIT",
                    confidence=0.45,
                    rationale=f"Committee veto from {', '.join(blockers)}.",
                    context={"blockers": blockers},
                ),
                0,
            )

        candidate = self._combine(market, llm)
        if candidate.action not in {"BUY", "SELL"}:
            return candidate, 0

        directional_votes = [decision for decision in [market, *committee] if decision.action in {"BUY", "SELL"}]
        agreeing = [decision for decision in directional_votes if decision.action == candidate.action]
        opposing = [decision for decision in directional_votes if decision.action != candidate.action]
        consensus_score = len(agreeing) / max(len(directional_votes), 1)
        avg_confidence = sum(decision.confidence for decision in agreeing) / max(len(agreeing), 1)

        if consensus_score < 0.66 or opposing:
            return (
                AgentDecisionOut(
                    agent_name="TradeCommittee",
                    symbol=market.symbol,
                    action="WAIT",
                    confidence=round(min(avg_confidence, 0.58), 2),
                    rationale=f"Consensus too weak: {consensus_score:.0%} agreement for {candidate.action}.",
                    context={
                        "candidate_action": candidate.action,
                        "agreeing_agents": [decision.agent_name for decision in agreeing],
                        "opposing_agents": [decision.agent_name for decision in opposing],
                    },
                ),
                consensus_score,
            )

        return (
            AgentDecisionOut(
                agent_name="TradeCommittee",
                symbol=market.symbol,
                action=candidate.action,
                confidence=round(min(avg_confidence, candidate.confidence, 0.95), 2),
                rationale=f"Committee approved {candidate.action} with {consensus_score:.0%} directional agreement.",
                context={
                    "agreeing_agents": [decision.agent_name for decision in agreeing],
                    "consensus_score": round(consensus_score, 2),
                },
            ),
            consensus_score,
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

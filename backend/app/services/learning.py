from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import LearningRule, Position
from app.schemas.dto import MarketCoin


@dataclass
class LearningAssessment:
    allowed: bool
    penalty: float
    reason: str


class LearningService:
    block_threshold = 2.5
    warn_threshold = 1.25
    max_penalty = 5.0
    min_observations_for_block = 2
    half_life_days = 14.0

    def entry_context(self, coin: MarketCoin, signal: str, reasons: list[str]) -> dict[str, Any]:
        atr_percent = self._atr_percent(float(coin.atr), float(coin.price))
        return {
            "symbol": coin.symbol,
            "side": "LONG" if signal == "BUY" else "SHORT",
            "signal": signal,
            "rating": coin.rating,
            "rsi": round(coin.rsi, 2),
            "rsi_bucket": self._rsi_bucket(coin.rsi),
            "atr_percent": round(atr_percent, 2),
            "atr_bucket": self._atr_bucket(atr_percent),
            "regime": coin.regime,
            "regime_score_bucket": self._score_bucket(coin.regime_score),
            "trend_stack": self._trend_stack(coin),
            "macd_direction": "positive" if coin.macd > 0 else "negative" if coin.macd < 0 else "flat",
            "rating_bucket": self._score_bucket(coin.rating),
            "reasons": reasons,
        }

    async def assess_entry(self, db: AsyncSession, coin: MarketCoin, signal: str) -> LearningAssessment:
        side = "LONG" if signal == "BUY" else "SHORT"
        features = self._features_from_context(self.entry_context(coin, signal, []))
        total_penalty = 0.0
        matched: list[str] = []
        for scope in ("GLOBAL", coin.symbol):
            rules = await self._rules_for(db, scope, side, features)
            for rule in rules:
                if rule.penalty > 0:
                    weight = 1.0 if scope == "GLOBAL" else 1.25
                    confidence = self.rule_confidence(rule.observations, rule.updated_at)
                    effective_penalty = rule.penalty * weight * confidence
                    total_penalty += effective_penalty
                    matched.append(f"{rule.feature_key}={rule.feature_value}:{effective_penalty:.2f}")
        if total_penalty >= self.block_threshold:
            return LearningAssessment(False, round(total_penalty, 2), f"learning guard blocked similar losing setup ({', '.join(matched[:4])})")
        if total_penalty >= self.warn_threshold:
            return LearningAssessment(True, round(total_penalty, 2), f"learning guard warning: similar setup has losses ({', '.join(matched[:4])})")
        return LearningAssessment(True, round(total_penalty, 2), "learning guard passed")

    async def record_closed_position(self, db: AsyncSession, position: Position, profit: float, reason: str) -> None:
        context = position.entry_context or {}
        side = str(context.get("side") or position.side)
        features = self._features_from_context(context)
        if reason:
            features.append(("exit_reason", reason))
        for scope in ("GLOBAL", position.symbol):
            for feature_key, feature_value in features:
                await self._upsert_rule(db, scope, side, feature_key, feature_value, profit, reason)

    async def _rules_for(
        self,
        db: AsyncSession,
        scope: str,
        side: str,
        features: list[tuple[str, str]],
    ) -> list[LearningRule]:
        if not features:
            return []
        keys = {key for key, _ in features}
        values = {value for _, value in features}
        result = await db.execute(
            select(LearningRule).where(
                LearningRule.scope == scope,
                LearningRule.side == side,
                LearningRule.feature_key.in_(keys),
                LearningRule.feature_value.in_(values),
            )
        )
        return [
            rule
            for rule in result.scalars().all()
            if (rule.feature_key, rule.feature_value) in features
        ]

    async def _upsert_rule(
        self,
        db: AsyncSession,
        scope: str,
        side: str,
        feature_key: str,
        feature_value: str,
        profit: float,
        reason: str,
    ) -> None:
        loss = profit < 0
        penalty_delta = self._penalty_delta(profit)
        statement = insert(LearningRule).values(
            scope=scope,
            side=side,
            feature_key=feature_key,
            feature_value=feature_value,
            penalty=max(penalty_delta, 0),
            observations=1,
            wins=0 if loss else 1,
            losses=1 if loss else 0,
            total_profit=profit,
            last_reason=reason,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_learning_rule",
            set_={
                "penalty": func.greatest(0, func.least(self.max_penalty, LearningRule.penalty + penalty_delta)),
                "observations": LearningRule.observations + 1,
                "wins": LearningRule.wins + (0 if loss else 1),
                "losses": LearningRule.losses + (1 if loss else 0),
                "total_profit": LearningRule.total_profit + profit,
                "last_reason": reason,
            },
        )
        await db.execute(statement)

    def _penalty_delta(self, profit: float) -> float:
        if profit < 0:
            return min(1.0, 0.35 + abs(profit) / 25)
        return -min(0.5, 0.15 + profit / 50)

    def rule_confidence(self, observations: int, updated_at: datetime | None = None) -> float:
        if observations <= 0:
            return 0.0
        observation_confidence = min(1.0, observations / self.min_observations_for_block)
        return round(observation_confidence * self.recency_weight(updated_at), 4)

    def risk_level(self, penalty: float, observations: int, updated_at: datetime | None = None) -> str:
        effective = penalty * self.rule_confidence(observations, updated_at)
        if effective >= self.block_threshold:
            return "BLOCK"
        if effective >= self.warn_threshold:
            return "WARN"
        return "WATCH"

    def recency_weight(self, updated_at: datetime | None) -> float:
        if not updated_at:
            return 1.0
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_days = max((datetime.now(timezone.utc) - updated_at).total_seconds() / 86400, 0)
        return round(0.5 ** (age_days / self.half_life_days), 4)

    def _features_from_context(self, context: dict[str, Any]) -> list[tuple[str, str]]:
        feature_keys = [
            "regime",
            "regime_score_bucket",
            "rsi_bucket",
            "atr_bucket",
            "trend_stack",
            "macd_direction",
            "rating_bucket",
        ]
        return [(key, str(context[key])) for key in feature_keys if context.get(key) is not None]

    def _atr_percent(self, atr: float, price: float) -> float:
        return atr / price * 100 if price > 0 else 0

    def _atr_bucket(self, value: float) -> str:
        if value < 0.75:
            return "quiet"
        if value <= 3.0:
            return "normal"
        if value <= 6.0:
            return "hot"
        return "extreme"

    def _rsi_bucket(self, value: float) -> str:
        if value < 30:
            return "oversold"
        if value < 45:
            return "bearish"
        if value <= 55:
            return "neutral"
        if value <= 70:
            return "bullish"
        return "overbought"

    def _score_bucket(self, value: float) -> str:
        if value < 45:
            return "weak"
        if value < 70:
            return "medium"
        if value < 85:
            return "strong"
        return "elite"

    def _trend_stack(self, coin: MarketCoin) -> str:
        if coin.ema20 > coin.ema50 > coin.ema200:
            return "bullish"
        if coin.ema20 < coin.ema50 < coin.ema200:
            return "bearish"
        return "mixed"

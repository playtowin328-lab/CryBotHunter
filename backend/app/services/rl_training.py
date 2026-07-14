from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env

from app.core.config import get_settings
from app.models.entities import AgentDecision, RlModel
from app.services.history import HistoricalDataService
from app.services.rl_environment import FEATURE_NAMES, CryptoTradingEnv, build_feature_frame, latest_observation


ACTION_NAMES = ("WAIT", "BUY", "SELL")


class RlTrainingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.history = HistoricalDataService()

    async def needs_refresh(self, db: AsyncSession, symbol: str, timeframe: str) -> bool:
        active = await self.active_for(db, symbol, timeframe)
        if not active or not active.created_at:
            return True
        created_at = active.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - created_at >= timedelta(hours=max(self.settings.rl_refresh_hours, 1.0))

    async def active_for(self, db: AsyncSession, symbol: str, timeframe: str) -> RlModel | None:
        return (
            await db.execute(
                select(RlModel)
                .where(RlModel.symbol == symbol, RlModel.timeframe == timeframe, RlModel.is_active.is_(True))
                .order_by(RlModel.created_at.desc())
                .limit(1)
            )
        ).scalars().first()

    async def train_symbol(self, db: AsyncSession, symbol: str, timeframe: str = "1h") -> RlModel:
        if not self.settings.uses_live_market_data:
            raise RuntimeError("RL training refuses synthetic market data; use MARKET_DATA_MODE=ccxt")
        limit = max(self.settings.rl_training_limit, self.settings.rl_min_training_candles)
        candles = await self.history.load(db, symbol, timeframe, limit=limit, source="ccxt")
        if len(candles) < self.settings.rl_min_training_candles:
            await self.history.ingest(db, symbol, timeframe, limit=limit)
            candles = await self.history.load(db, symbol, timeframe, limit=limit, source="ccxt")
        if len(candles) < self.settings.rl_min_training_candles:
            raise RuntimeError(
                f"not enough real candles for RL: {len(candles)}/{self.settings.rl_min_training_candles}"
            )

        frame = build_feature_frame(candles)
        train_frame, validation_frame = self._split(frame)
        check_env(self._environment(train_frame), warn=True)

        candidates: list[tuple[float, PPO, dict]] = []
        for seed in self.settings.rl_training_seeds:
            model = PPO(
                "MlpPolicy",
                self._environment(train_frame),
                learning_rate=3e-4,
                n_steps=512,
                batch_size=64,
                gamma=0.995,
                gae_lambda=0.95,
                ent_coef=0.005,
                policy_kwargs={"net_arch": [64, 64]},
                seed=seed,
                device="cpu",
                verbose=0,
            )
            model.learn(total_timesteps=max(self.settings.rl_training_timesteps, 1_000), progress_bar=False)
            metrics = self._evaluate(model, validation_frame)
            metrics["seed"] = seed
            score = (
                float(metrics["return_percent"])
                - float(metrics["max_drawdown_percent"]) * 0.5
                + min(float(metrics["profit_factor"]), 5.0)
            )
            candidates.append((score, model, metrics))

        _, best_model, metrics = max(candidates, key=lambda item: item[0])
        metrics["buy_hold_return_percent"] = self._buy_hold_return(validation_frame)
        metrics["market_data_source"] = "ccxt"
        metrics["passed"] = self._passes_promotion(metrics)
        metrics["promotion_reason"] = self._promotion_reason(metrics)
        artifact = self._serialize(best_model)

        promoted = bool(metrics["passed"])
        if promoted:
            await db.execute(
                update(RlModel)
                .where(RlModel.symbol == symbol, RlModel.timeframe == timeframe, RlModel.is_active.is_(True))
                .values(is_active=False, status="RETIRED")
            )
        record = RlModel(
            symbol=symbol,
            timeframe=timeframe,
            algorithm="PPO",
            status="ACTIVE" if promoted else "REJECTED",
            is_active=promoted,
            training_candles=len(train_frame),
            validation_candles=len(validation_frame),
            metrics=metrics,
            feature_schema={"features": FEATURE_NAMES, "actions": list(ACTION_NAMES), "version": 1},
            artifact=artifact,
        )
        db.add(record)
        await db.flush()
        if promoted:
            self._store_decision(db, record, best_model, frame)
        await db.commit()
        await db.refresh(record)
        return record

    async def publish_active_decision(self, db: AsyncSession, symbol: str, timeframe: str = "1h") -> AgentDecision | None:
        model_record = await self.active_for(db, symbol, timeframe)
        if not model_record or not model_record.artifact:
            return None
        await self.history.ingest(db, symbol, timeframe, limit=300)
        candles = await self.history.load(db, symbol, timeframe, limit=300, source="ccxt")
        frame = build_feature_frame(candles)
        if len(frame) < 100:
            return None
        model = self._deserialize(model_record.artifact)
        decision = self._store_decision(db, model_record, model, frame)
        await db.commit()
        return decision

    def _split(self, frame):
        percent = min(max(self.settings.rl_validation_percent, 10.0), 40.0)
        validation_size = max(300, int(len(frame) * percent / 100))
        train_size = len(frame) - validation_size
        if train_size < 1_000 or validation_size < 300:
            raise RuntimeError(f"RL split is too small: train={train_size}, validation={validation_size}")
        return frame.iloc[:train_size].reset_index(drop=True), frame.iloc[train_size:].reset_index(drop=True)

    def _environment(self, frame) -> CryptoTradingEnv:
        return CryptoTradingEnv(
            frame,
            fee_rate=self.settings.paper_fee_rate,
            slippage_bps=self.settings.paper_slippage_bps,
        )

    def _evaluate(self, model: PPO, frame) -> dict:
        env = self._environment(frame)
        observation, _ = env.reset()
        terminated = False
        truncated = False
        info = env.metrics()
        while not (terminated or truncated):
            action, _ = model.predict(observation, deterministic=True)
            observation, _, terminated, truncated, info = env.step(int(action))
        return dict(info)

    def _passes_promotion(self, metrics: dict) -> bool:
        return (
            float(metrics["return_percent"]) >= self.settings.rl_min_validation_return_percent
            and float(metrics["profit_factor"]) >= self.settings.rl_min_validation_profit_factor
            and int(metrics["trades"]) >= self.settings.rl_min_validation_trades
            and float(metrics["max_drawdown_percent"]) <= self.settings.rl_max_validation_drawdown_percent
        )

    def _promotion_reason(self, metrics: dict) -> str:
        reasons: list[str] = []
        if float(metrics["return_percent"]) < self.settings.rl_min_validation_return_percent:
            reasons.append("validation return below threshold")
        if float(metrics["profit_factor"]) < self.settings.rl_min_validation_profit_factor:
            reasons.append("validation profit factor below threshold")
        if int(metrics["trades"]) < self.settings.rl_min_validation_trades:
            reasons.append("too few validation trades")
        if float(metrics["max_drawdown_percent"]) > self.settings.rl_max_validation_drawdown_percent:
            reasons.append("validation drawdown above threshold")
        return "passed" if not reasons else "; ".join(reasons)

    def _buy_hold_return(self, frame) -> float:
        first = max(float(frame.iloc[0]["close"]), 1e-12)
        last = max(float(frame.iloc[-1]["close"]), 1e-12)
        return round((last / first - 1) * 100, 4)

    def _store_decision(self, db: AsyncSession, record: RlModel, model: PPO, frame) -> AgentDecision:
        observation = latest_observation(frame)
        action, _ = model.predict(observation, deterministic=True)
        action_index = int(action)
        confidence = self._confidence(model, observation, action_index)
        decision = AgentDecision(
            agent_name="rl_policy",
            symbol=record.symbol,
            action=ACTION_NAMES[action_index],
            confidence=confidence,
            rationale=f"Promoted PPO model #{record.id} evaluated current real-market features",
            context={
                "model_id": record.id,
                "algorithm": record.algorithm,
                "timeframe": record.timeframe,
                "market_data_source": "ccxt",
                "validation": record.metrics,
            },
        )
        db.add(decision)
        return decision

    def _confidence(self, model: PPO, observation: np.ndarray, action_index: int) -> float:
        observation_tensor, _ = model.policy.obs_to_tensor(observation)
        distribution = model.policy.get_distribution(observation_tensor)
        probabilities = distribution.distribution.probs.detach().cpu().numpy()[0]
        return round(float(probabilities[action_index]), 4)

    def _serialize(self, model: PPO) -> bytes:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "model.zip"
            model.save(path)
            return path.read_bytes()

    def _deserialize(self, artifact: bytes) -> PPO:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "model.zip"
            path.write_bytes(artifact)
            return PPO.load(path, device="cpu")

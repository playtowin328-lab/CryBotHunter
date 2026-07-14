import asyncio
import logging

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.entities import LogEntry
from app.services.locks import RedisLockManager
from app.services.rl_training import RlTrainingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    trainer = RlTrainingService()
    locks = RedisLockManager()
    logger.info(
        "RL worker started symbols=%s timeframes=%s loop=%ss",
        settings.candle_ingest_symbols,
        settings.candle_ingest_timeframes,
        settings.rl_prediction_loop_seconds,
    )
    while True:
        try:
            if not settings.rl_trainer_enabled:
                logger.warning("RL worker disabled by RL_TRAINER_ENABLED=false")
            else:
                async with AsyncSessionLocal() as db:
                    async with locks.lock("rl-worker-loop", ttl_seconds=max(settings.rl_prediction_loop_seconds - 5, 60)) as acquired:
                        if acquired:
                            for symbol in settings.candle_ingest_symbols:
                                for timeframe in settings.candle_ingest_timeframes:
                                    key = f"{symbol}:{timeframe}"
                                    try:
                                        if await trainer.needs_refresh(db, symbol, timeframe):
                                            model = await trainer.train_symbol(db, symbol, timeframe)
                                            logger.info("RL trained %s status=%s metrics=%s", key, model.status, model.metrics)
                                            db.add(LogEntry(level="INFO", message=f"RL trained {key}: status={model.status}"))
                                            await db.commit()
                                        else:
                                            decision = await trainer.publish_active_decision(db, symbol, timeframe)
                                            if decision:
                                                logger.info("RL decision %s action=%s confidence=%.2f", key, decision.action, decision.confidence)
                                    except Exception as exc:
                                        logger.exception("RL worker failed for %s", key)
                                        await db.rollback()
                                        db.add(LogEntry(level="ERROR", message=f"RL worker failed for {key}: {exc.__class__.__name__}"))
                                        await db.commit()
        except Exception:
            logger.exception("RL worker loop failed")
        await asyncio.sleep(max(settings.rl_prediction_loop_seconds, 60))


if __name__ == "__main__":
    asyncio.run(main())

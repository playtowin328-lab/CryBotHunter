import asyncio
import logging

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.entities import LogEntry
from app.services.history import HistoricalDataService
from app.services.locks import RedisLockManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    history = HistoricalDataService()
    locks = RedisLockManager()
    logger.info(
        "Candle worker started symbols=%s timeframes=%s loop=%ss",
        settings.candle_ingest_symbols,
        settings.candle_ingest_timeframes,
        settings.candle_ingest_loop_seconds,
    )
    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with locks.lock("candle-worker-loop", ttl_seconds=max(settings.candle_ingest_loop_seconds - 5, 30)) as acquired:
                    if acquired:
                        inserted = await history.ingest_many(
                            db,
                            symbols=settings.candle_ingest_symbols,
                            timeframes=settings.candle_ingest_timeframes,
                            limit=min(settings.candle_ingest_limit, 1000),
                        )
                        total = sum(inserted.values())
                        db.add(LogEntry(level="INFO", message=f"Candle worker inserted {total} candle(s): {inserted}"))
                        await db.commit()
        except Exception:
            logger.exception("Candle worker loop failed")
        await asyncio.sleep(settings.candle_ingest_loop_seconds)


if __name__ == "__main__":
    asyncio.run(main())

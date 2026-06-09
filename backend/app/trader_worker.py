import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.entities import LogEntry, UserSettings
from app.services.control import TradingControlService
from app.services.locks import RedisLockManager
from app.services.reconciliation import OrderReconciliationService
from app.services.risk_manager import RiskSettings
from app.services.trading_engine import TradingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    engine = TradingEngine()
    locks = RedisLockManager()
    control = TradingControlService()
    reconciliation = OrderReconciliationService()
    logger.info("Trader worker started with loop=%ss", settings.trader_loop_seconds)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                async with locks.lock("trader-worker-loop", ttl_seconds=max(settings.trader_loop_seconds - 5, 10)) as acquired:
                    if acquired:
                        await engine.manage_open_positions(db)
                        await reconciliation.reconcile(db)
                        paused, reason = await control.is_paused()
                        if paused:
                            logger.warning("Trader worker entry scan paused: %s", reason)
                            await asyncio.sleep(settings.trader_loop_seconds)
                            continue
                        user_settings = (await db.execute(select(UserSettings).order_by(UserSettings.id.asc()).limit(1))).scalar_one_or_none()
                        if user_settings:
                            risk_settings = RiskSettings(
                                balance=1000,
                                risk_percent=user_settings.risk_percent,
                                daily_risk_percent=user_settings.daily_risk_percent,
                                max_positions=user_settings.max_positions,
                                min_rating=user_settings.min_rating,
                                stop_loss_percent=user_settings.stop_loss_percent,
                                take_profit_percent=user_settings.take_profit_percent,
                                trailing_stop_percent=user_settings.trailing_stop_percent,
                            )
                            await engine.run_once(db, risk_settings)
                        else:
                            db.add(LogEntry(level="WARNING", message="Trader worker is waiting for the first user settings row"))
                            await db.commit()
        except Exception:
            logger.exception("Trader worker loop failed")
        await asyncio.sleep(settings.trader_loop_seconds)


if __name__ == "__main__":
    asyncio.run(main())

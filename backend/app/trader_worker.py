import asyncio
import logging

import ccxt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.db.session import AsyncSessionLocal
from app.models.entities import LogEntry, UserSettings
from app.safety_manager import SafetyCredentials, SafetyManager, ShutdownController, configure_stdout_logging
from app.services.control import TradingControlService
from app.services.exchange import ExchangeClient, exchange_error_message
from app.services.locks import RedisLockManager
from app.services.reconciliation import OrderReconciliationService
from app.services.risk_manager import RiskSettings
from app.services.trading_engine import TradingEngine

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_stdout_logging()
    shutdown = ShutdownController()
    shutdown.install()
    safety_credentials = await _load_safety_credentials()
    await SafetyManager().run_or_exit(safety_credentials)
    if shutdown.requested:
        return

    settings = get_settings()
    locks = RedisLockManager()
    control = TradingControlService()
    logger.info("Trader worker started with loop=%ss", settings.trader_loop_seconds)
    while not shutdown.requested:
        current_exchange = settings.default_exchange
        exchange: ExchangeClient | None = None
        delay = settings.trader_loop_seconds
        try:
            async with AsyncSessionLocal() as db:
                async with locks.lock("trader-worker-loop", ttl_seconds=max(settings.trader_loop_seconds - 5, 10)) as acquired:
                    if acquired:
                        user_settings = (await db.execute(select(UserSettings).order_by(UserSettings.id.asc()).limit(1))).scalar_one_or_none()
                        if not user_settings:
                            db.add(LogEntry(level="WARNING", message="Trader worker is waiting for the first user settings row"))
                            await db.commit()
                        else:
                            current_exchange = user_settings.exchange
                            exchange = ExchangeClient.from_user_settings(user_settings)
                            engine = TradingEngine(exchange)
                            reconciliation = OrderReconciliationService(exchange)
                            tick = await engine.manage_open_positions(db)
                            await reconciliation.reconcile(db)
                            paused, reason = await control.is_paused()
                            if paused:
                                logger.warning("Trader worker entry scan paused: %s", reason)
                            elif not shutdown.requested:
                                risk_settings = RiskSettings(
                                    balance=1000,
                                    risk_percent=user_settings.risk_percent,
                                    daily_risk_percent=user_settings.daily_risk_percent,
                                    max_positions=user_settings.max_positions,
                                    min_rating=user_settings.min_rating,
                                    stop_loss_percent=user_settings.stop_loss_percent,
                                    take_profit_percent=user_settings.take_profit_percent,
                                    trailing_stop_percent=user_settings.trailing_stop_percent,
                                    atr_stop_multiplier=user_settings.atr_stop_multiplier,
                                    risk_reward_ratio=user_settings.risk_reward_ratio,
                                    breakeven_trigger_r=user_settings.breakeven_trigger_r,
                                    breakeven_offset_percent=user_settings.breakeven_offset_percent,
                                    partial_take_profit_r=user_settings.partial_take_profit_r,
                                    partial_close_percent=user_settings.partial_close_percent,
                                )
                                run = await engine.run_once(db, risk_settings, timeframe=user_settings.scan_interval)
                                summary = _cycle_summary(run.scanned, run.opened, run.skipped, run.decisions, tick.closed)
                                logger.info(summary)
                                db.add(LogEntry(level="INFO", message=summary))
                                await db.commit()
        except ccxt.BaseError as exc:
            message = exchange_error_message(
                exc,
                exchange=current_exchange,
                market_type=settings.exchange_default_type,
                sandbox=settings.exchange_sandbox_enabled,
            )
            logger.error("Trader worker exchange unavailable: %s", message)
            await _record_worker_log(message)
            delay = max(settings.trader_loop_seconds, 300)
        except Exception:
            logger.exception("Trader worker loop failed")
        finally:
            if exchange is not None:
                await exchange.close()
        if await shutdown.wait(delay):
            break
    logger.info("Trader worker shutdown complete")


async def _load_safety_credentials() -> SafetyCredentials | None:
    async with AsyncSessionLocal() as db:
        user_settings = (
            await db.execute(select(UserSettings).order_by(UserSettings.id.asc()).limit(1))
        ).scalar_one_or_none()
    if user_settings is None:
        return None
    return SafetyCredentials(
        exchange=user_settings.exchange,
        api_key=decrypt_secret(user_settings.api_key_encrypted),
        api_secret=decrypt_secret(user_settings.secret_key_encrypted),
        passphrase=decrypt_secret(user_settings.passphrase_encrypted),
    )


def _cycle_summary(scanned: int, opened: int, skipped: int, decisions: list, closed: int) -> str:
    samples = "; ".join(
        f"{decision.symbol}={decision.signal}/{decision.action}({decision.score}): {decision.reason}"
        for decision in decisions[:3]
    )
    message = (
        f"Auto-trade cycle scanned={scanned} opened={opened} skipped={skipped} "
        f"closed={closed} learning_updates={closed}"
    )
    return f"{message}; {samples}"[:1000] if samples else message


async def _record_worker_log(message: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            db.add(LogEntry(level="ERROR", message=f"Trader worker exchange unavailable: {message[:900]}"))
            await db.commit()
    except Exception:
        logger.exception("Failed to record trader worker exchange error")


if __name__ == "__main__":
    asyncio.run(main())

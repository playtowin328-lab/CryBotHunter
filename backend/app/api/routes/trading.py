from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import Position, User, UserSettings
from app.schemas.dto import ActionMessage, BacktestOut, SystemStatusOut, TradingRunOut, TradingTickOut
from app.services.backtesting import BacktestingService
from app.services.control import TradingControlService
from app.services.history import HistoricalDataService
from app.services.locks import RedisLockManager
from app.services.risk_manager import RiskSettings
from app.services.trading_engine import TradingEngine

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/run-once", response_model=TradingRunOut)
async def run_once(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> TradingRunOut:
    paused, _reason = await TradingControlService().is_paused()
    if paused:
        return TradingRunOut(scanned=0, opened=0, skipped=0, decisions=[])
    user_settings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one()
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
    async with RedisLockManager().lock("trading-run", ttl_seconds=55) as acquired:
        if not acquired:
            return TradingRunOut(scanned=0, opened=0, skipped=0, decisions=[])
        return await TradingEngine().run_once(db, risk_settings)


@router.post("/tick", response_model=TradingTickOut)
async def tick(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> TradingTickOut:
    async with RedisLockManager().lock("trading-tick", ttl_seconds=55) as acquired:
        if not acquired:
            return TradingTickOut(checked=0, closed=0, updated=[])
        return await TradingEngine().manage_open_positions(db)


@router.get("/status", response_model=SystemStatusOut)
async def status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> SystemStatusOut:
    settings = get_settings()
    paused, panic_reason = await TradingControlService().is_paused()
    user_settings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one()
    open_positions = (
        await db.execute(select(func.count()).select_from(Position).where(Position.status == "OPEN"))
    ).scalar_one()
    daily_pnl = await db.execute(select(func.coalesce(func.sum(Position.pnl), 0.0)).where(Position.status == "OPEN"))
    return SystemStatusOut(
        paper_trading=settings.paper_trading,
        exchange=user_settings.exchange,
        telegram_enabled=bool(settings.telegram_bot_token),
        telegram_chat_count=len(settings.telegram_allowed_chat_ids),
        open_positions=int(open_positions),
        daily_pnl=float(daily_pnl.scalar_one()),
        panic_paused=paused,
        panic_reason=panic_reason,
    )


@router.post("/panic", response_model=ActionMessage)
async def panic(_: User = Depends(current_user), reason: str = "manual") -> ActionMessage:
    await TradingControlService().panic(reason)
    return ActionMessage(ok=True, message=f"Trading entry scans paused: {reason}")


@router.post("/resume", response_model=ActionMessage)
async def resume(_: User = Depends(current_user)) -> ActionMessage:
    await TradingControlService().resume()
    return ActionMessage(ok=True, message="Trading entry scans resumed")


@router.get("/backtest/sample", response_model=BacktestOut)
async def sample_backtest(_: User = Depends(current_user)) -> BacktestOut:
    report = BacktestingService().summarize([12, -5, 18, 7, -9, 15, -4, 11, 3, -6])
    return BacktestOut(**report.__dict__)


@router.post("/backtest", response_model=BacktestOut)
async def run_backtest(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 500,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> BacktestOut:
    history = HistoricalDataService()
    candles = await history.load(db, symbol=symbol, timeframe=timeframe, limit=min(limit, 1000))
    if len(candles) < 220:
        await history.ingest(db, symbol=symbol, timeframe=timeframe, limit=min(limit, 1000))
        candles = await history.load(db, symbol=symbol, timeframe=timeframe, limit=min(limit, 1000))
    report = BacktestingService().run(candles)
    return BacktestOut(**report.__dict__)

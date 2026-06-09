from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import Position, User, UserSettings
from app.schemas.dto import BacktestOut, SystemStatusOut, TradingRunOut, TradingTickOut
from app.services.backtesting import BacktestingService
from app.services.risk_manager import RiskSettings
from app.services.trading_engine import TradingEngine

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/run-once", response_model=TradingRunOut)
async def run_once(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> TradingRunOut:
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
    return await TradingEngine().run_once(db, risk_settings)


@router.post("/tick", response_model=TradingTickOut)
async def tick(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> TradingTickOut:
    return await TradingEngine().manage_open_positions(db)


@router.get("/status", response_model=SystemStatusOut)
async def status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> SystemStatusOut:
    settings = get_settings()
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
    )


@router.get("/backtest/sample", response_model=BacktestOut)
async def sample_backtest(_: User = Depends(current_user)) -> BacktestOut:
    report = BacktestingService().summarize([12, -5, 18, 7, -9, 15, -4, 11, 3, -6])
    return BacktestOut(**report.__dict__)

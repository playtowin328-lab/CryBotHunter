from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import User, UserSettings
from app.schemas.dto import StrategySignal
from app.services.risk_manager import RiskSettings
from app.services.trading_engine import TradingEngine

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/run-once", response_model=list[StrategySignal])
async def run_once(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[StrategySignal]:
    user_settings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one()
    risk_settings = RiskSettings(
        balance=1000,
        risk_percent=user_settings.risk_percent,
        daily_risk_percent=user_settings.daily_risk_percent,
        max_positions=user_settings.max_positions,
        min_rating=user_settings.min_rating,
        stop_loss_percent=user_settings.stop_loss_percent,
        take_profit_percent=user_settings.take_profit_percent,
    )
    signals = await TradingEngine().run_once(db, risk_settings)
    return [StrategySignal(symbol=item.symbol, signal=item.signal, score=item.score) for item in signals]

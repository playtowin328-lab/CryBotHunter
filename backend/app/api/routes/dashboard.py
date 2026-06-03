from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import Position, Trade, User
from app.schemas.dto import DashboardOut
from app.services.exchange import ExchangeClient

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def dashboard(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> DashboardOut:
    balance = (await ExchangeClient().get_balance()).get("USDT", 0)
    positions = (await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.desc()))).scalars().all()
    trades = await db.execute(select(func.count(Trade.id), func.coalesce(func.sum(Trade.profit), 0.0)))
    trades_count, pnl = trades.one()
    wins = await db.execute(select(func.count(Trade.id)).where(Trade.profit > 0))
    win_rate = (int(wins.scalar_one()) / trades_count * 100) if trades_count else 0
    return DashboardOut(
        balance=balance,
        pnl_day=float(pnl),
        pnl_week=float(pnl),
        win_rate=round(win_rate, 2),
        trades_count=int(trades_count),
        active_positions=list(positions),
    )

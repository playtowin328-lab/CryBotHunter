from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import Position, User
from app.schemas.dto import DashboardOut
from app.services.exchange import ExchangeClient
from app.services.pnl import PnlMetricsService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def dashboard(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> DashboardOut:
    balance = (await ExchangeClient().get_balance()).get("USDT", 0)
    positions = (await db.execute(select(Position).where(Position.status == "OPEN").order_by(Position.entered_at.desc()))).scalars().all()
    pnl = await PnlMetricsService().summary(db)
    return DashboardOut(
        balance=balance,
        pnl_day=pnl.pnl_day,
        pnl_week=pnl.pnl_week,
        win_rate=pnl.win_rate,
        trades_count=pnl.trades_count,
        active_positions=list(positions),
    )

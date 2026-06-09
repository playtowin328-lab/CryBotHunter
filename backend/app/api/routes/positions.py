from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import LogEntry, Position, Trade, User
from app.schemas.dto import PositionOut

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionOut])
async def list_positions(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> list[Position]:
    return list((await db.execute(select(Position).order_by(Position.entered_at.desc()))).scalars().all())


@router.post("/{position_id}/close", response_model=PositionOut)
async def close_position(position_id: int, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Position:
    position = (await db.execute(select(Position).where(Position.id == position_id))).scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    position.status = "CLOSED"
    position.exit_reason = "MANUAL"
    position.closed_at = datetime.now(timezone.utc)
    multiplier = 1 if position.side == "LONG" else -1
    position.pnl = (position.current_price - position.entry_price) * position.volume * multiplier
    trade = (
        await db.execute(
            select(Trade)
            .where(Trade.symbol == position.symbol, Trade.exit_price.is_(None))
            .order_by(Trade.created_at.desc())
        )
    ).scalars().first()
    if trade:
        trade.exit_price = position.current_price
        trade.profit = position.pnl
    db.add(LogEntry(level="INFO", message=f"Closed position {position.symbol} #{position.id}"))
    await db.commit()
    await db.refresh(position)
    return position

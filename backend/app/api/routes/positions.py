from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import LogEntry, Position, User
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
    multiplier = 1 if position.side == "LONG" else -1
    position.pnl = (position.current_price - position.entry_price) * position.volume * multiplier
    db.add(LogEntry(level="INFO", message=f"Closed position {position.symbol} #{position.id}"))
    await db.commit()
    await db.refresh(position)
    return position

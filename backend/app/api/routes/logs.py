from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import LogEntry, User
from app.schemas.dto import LogOut

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[LogOut])
async def logs(_: User = Depends(current_user), db: AsyncSession = Depends(get_db), limit: int = 100) -> list[LogEntry]:
    query = select(LogEntry).order_by(LogEntry.created_at.desc()).limit(min(limit, 500))
    return list((await db.execute(query)).scalars().all())

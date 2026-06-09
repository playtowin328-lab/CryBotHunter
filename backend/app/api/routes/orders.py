from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import Order, User
from app.schemas.dto import OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
async def list_orders(_: User = Depends(current_user), db: AsyncSession = Depends(get_db), limit: int = 50) -> list[Order]:
    result = await db.execute(select(Order).order_by(Order.created_at.desc()).limit(min(limit, 200)))
    return list(result.scalars().all())

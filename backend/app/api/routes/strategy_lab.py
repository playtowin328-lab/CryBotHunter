from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from app.models.entities import User
from app.schemas.dto import StrategyOptimizationOut
from app.services.optimizer import StrategyOptimizerService

router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])


@router.post("/optimize", response_model=list[StrategyOptimizationOut])
async def optimize(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 500,
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StrategyOptimizationOut]:
    bounded_limit = max(220, min(limit, 1000))
    return await StrategyOptimizerService().optimize(db, symbol=symbol, timeframe=timeframe, limit=bounded_limit)


@router.get("/results", response_model=list[StrategyOptimizationOut])
async def results(_: User = Depends(current_user), db: AsyncSession = Depends(get_db), limit: int = 20) -> list[StrategyOptimizationOut]:
    bounded_limit = max(1, min(limit, 100))
    return await StrategyOptimizerService().recent(db, limit=bounded_limit)

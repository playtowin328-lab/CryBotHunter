from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.db.session import get_db
from sqlalchemy import select

from app.models.entities import LearningRule, User
from app.schemas.dto import LearningRuleOut, StrategyOptimizationOut
from app.services.learning import LearningService
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


@router.get("/learning-rules", response_model=list[LearningRuleOut])
async def learning_rules(_: User = Depends(current_user), db: AsyncSession = Depends(get_db), limit: int = 50) -> list[LearningRuleOut]:
    bounded_limit = max(1, min(limit, 200))
    result = await db.execute(
        select(LearningRule)
        .order_by(LearningRule.penalty.desc(), LearningRule.updated_at.desc())
        .limit(bounded_limit)
    )
    service = LearningService()
    return [
        LearningRuleOut(
            **rule.__dict__,
            confidence=round(service.rule_confidence(rule.observations), 2),
            risk_level=service.risk_level(rule.penalty, rule.observations),
        )
        for rule in result.scalars().all()
    ]

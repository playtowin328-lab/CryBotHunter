from fastapi import APIRouter, Depends

from app.api.deps import current_user
from app.models.entities import User
from app.schemas.dto import MarketCoin, MlPrediction, StrategySignal
from app.services.market_scanner import MarketScanner
from app.services.ml import MlSignalService
from app.services.strategy import StrategyCore

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/scan", response_model=list[MarketCoin])
async def scan_market(_: User = Depends(current_user)) -> list[MarketCoin]:
    return await MarketScanner().scan()


@router.get("/signals", response_model=list[StrategySignal])
async def signals(_: User = Depends(current_user)) -> list[StrategySignal]:
    coins = await MarketScanner().scan()
    strategy = StrategyCore()
    return [strategy.evaluate(coin) for coin in coins]


@router.get("/ml", response_model=list[MlPrediction])
async def ml_predictions(_: User = Depends(current_user)) -> list[MlPrediction]:
    coins = await MarketScanner().scan()
    service = MlSignalService()
    return [service.predict(coin) for coin in coins]

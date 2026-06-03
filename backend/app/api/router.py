from fastapi import APIRouter

from app.api.routes import auth, dashboard, logs, market, positions, settings, trading

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(market.router)
api_router.include_router(positions.router)
api_router.include_router(settings.router)
api_router.include_router(logs.router)
api_router.include_router(trading.router)

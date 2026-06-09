from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse
from sqlalchemy import text
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.control import TradingControlService
from app.services.scheduler import create_scheduler

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
scheduler = create_scheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/deep")
async def deep_health() -> dict[str, object]:
    checks: dict[str, object] = {"status": "ok"}
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["status"] = "degraded"
        checks["database"] = f"error: {exc.__class__.__name__}"
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["status"] = "degraded"
        checks["redis"] = f"error: {exc.__class__.__name__}"
    paused, reason = await TradingControlService().is_paused()
    checks["panic_paused"] = paused
    checks["panic_reason"] = reason
    checks["paper_trading"] = settings.paper_trading
    checks["market_data_mode"] = settings.market_data_mode
    checks["llm_provider"] = settings.llm_provider
    return checks


app.include_router(api_router, prefix=settings.api_prefix)

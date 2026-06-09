from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


class TradingControlService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)

    async def panic(self, reason: str = "manual") -> bool:
        await self.redis.set(self.settings.trading_panic_key, reason)
        return True

    async def resume(self) -> bool:
        await self.redis.delete(self.settings.trading_panic_key)
        return True

    async def is_paused(self) -> tuple[bool, str | None]:
        try:
            reason = await self.redis.get(self.settings.trading_panic_key)
            return bool(reason), reason
        except RedisError:
            return False, None

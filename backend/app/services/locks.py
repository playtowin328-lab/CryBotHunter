from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisLockManager:
    def __init__(self) -> None:
        self.redis = Redis.from_url(get_settings().redis_url, decode_responses=True)

    @asynccontextmanager
    async def lock(self, name: str, ttl_seconds: int = 55) -> AsyncGenerator[bool, None]:
        key = f"lock:{name}"
        acquired = False
        redis_available = True
        try:
            acquired = bool(await self.redis.set(key, "1", nx=True, ex=ttl_seconds))
        except RedisError:
            redis_available = False
            acquired = False
            logger.exception("Redis lock unavailable, skipping protected operation: %s", name)
        try:
            yield acquired
        finally:
            if acquired and redis_available:
                try:
                    await self.redis.delete(key)
                except RedisError:
                    logger.exception("Redis lock release failed; TTL will expire the lock: %s", name)

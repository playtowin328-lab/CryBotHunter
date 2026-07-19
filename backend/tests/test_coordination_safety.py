import pytest
from redis.exceptions import RedisError

from app.services.control import TradingControlService
from app.services.locks import RedisLockManager


class UnavailableRedis:
    async def get(self, *_args, **_kwargs):
        raise RedisError("unavailable")

    async def set(self, *_args, **_kwargs):
        raise RedisError("unavailable")

    async def delete(self, *_args, **_kwargs):
        raise RedisError("unavailable")


@pytest.mark.asyncio
async def test_control_fails_closed_when_redis_is_unavailable():
    control = TradingControlService()
    control.redis = UnavailableRedis()

    assert await control.is_paused() == (True, "redis_unavailable")
    assert await control.panic("test") is False
    assert await control.resume() is False


@pytest.mark.asyncio
async def test_distributed_lock_skips_operation_when_redis_is_unavailable():
    locks = RedisLockManager()
    locks.redis = UnavailableRedis()

    async with locks.lock("trader-worker-loop") as acquired:
        assert acquired is False

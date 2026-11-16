import uuid
from typing import TYPE_CHECKING

from ai_workspace_api.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class DistributedLock:
    """Redis-based distributed lock with owner verification and safe release."""

    def __init__(
        self,
        redis: "Redis | None",
        key: str,
        ttl_seconds: int = 300,
    ) -> None:
        self.redis = redis
        self.key = key
        self.ttl_seconds = ttl_seconds
        self.token = str(uuid.uuid4())
        self._acquired = False

    async def acquire(self) -> bool:
        """Attempt to acquire the distributed lock."""
        if self.redis is None:
            # Fallback when Redis is not configured: grant in-process lock
            self._acquired = True
            return True

        try:
            acquired = await self.redis.set(
                self.key,
                self.token,
                nx=True,
                ex=self.ttl_seconds,
            )
            self._acquired = bool(acquired)
            return self._acquired
        except Exception as exc:
            logger.warning("distributed_lock.acquire_failed", key=self.key, error=str(exc))
            # If Redis connection fails, allow execution with warning
            self._acquired = True
            return True

    async def release(self) -> bool:
        """Release the lock if and only if this instance holds the token."""
        if not self._acquired or self.redis is None:
            self._acquired = False
            return True

        try:
            result = await self.redis.eval(
                RELEASE_LUA,
                1,
                self.key,
                self.token,
            )
            self._acquired = False
            return bool(result)
        except Exception as exc:
            logger.warning("distributed_lock.release_failed", key=self.key, error=str(exc))
            self._acquired = False
            return False

    async def is_locked(self) -> bool:
        if self.redis is None:
            return False
        try:
            val = await self.redis.get(self.key)
            return val is not None
        except Exception:
            return False

    async def __aenter__(self) -> bool:
        return await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        await self.release()

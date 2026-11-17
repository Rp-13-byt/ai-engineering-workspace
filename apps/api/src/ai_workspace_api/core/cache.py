from collections.abc import AsyncIterator

import redis.asyncio as redis

from ai_workspace_api.core.config import get_settings


settings = get_settings()
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis() -> AsyncIterator[redis.Redis]:
    yield redis_client

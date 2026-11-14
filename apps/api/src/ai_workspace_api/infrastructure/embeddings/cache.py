import hashlib
import json
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from ai_workspace_api.core.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


class EmbeddingCache:
    """Embedding cache supporting Redis with an in-memory LRU fallback."""

    def __init__(
        self,
        redis: "Redis | None" = None,
        max_memory_entries: int = 2000,
        ttl_seconds: int = 86400 * 7,
    ) -> None:
        self._redis = redis
        self._memory_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._max_memory_entries = max_memory_entries
        self._ttl_seconds = ttl_seconds

    def make_key(self, provider: str, model_name: str, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"embed:{provider}:{model_name}:{digest}"

    async def get_many(
        self,
        provider: str,
        model_name: str,
        texts: list[str],
    ) -> tuple[dict[int, list[float]], list[tuple[int, str]]]:
        """Look up embeddings for texts.

        Returns:
            hits: mapping from original text index to embedding vector.
            misses: list of (original index, text) pairs that need embedding.
        """
        hits: dict[int, list[float]] = {}
        misses: list[tuple[int, str]] = []

        keys = [self.make_key(provider, model_name, text) for text in texts]

        # 1. Try Redis first if connected
        redis_results: list[Any] = []
        if self._redis is not None:
            try:
                redis_results = await self._redis.mget(keys)
            except Exception as exc:
                logger.warning("embedding_cache.redis_mget_failed", error=str(exc))
                redis_results = [None] * len(keys)
        else:
            redis_results = [None] * len(keys)

        for idx, (text, key, redis_val) in enumerate(zip(texts, keys, redis_results, strict=True)):
            if redis_val is not None:
                try:
                    hits[idx] = json.loads(redis_val)
                    continue
                except Exception as exc:
                    logger.warning("embedding_cache.json_decode_failed", error=str(exc))

            # 2. Check in-memory fallback
            if key in self._memory_cache:
                self._memory_cache.move_to_end(key)
                hits[idx] = self._memory_cache[key]
            else:
                misses.append((idx, text))

        return hits, misses

    async def put_many(
        self,
        provider: str,
        model_name: str,
        indexed_vectors: list[tuple[int, str, list[float]]],
    ) -> None:
        """Cache newly computed embeddings."""
        if not indexed_vectors:
            return

        redis_mapping: dict[str, str] = {}
        for _, text, vector in indexed_vectors:
            key = self.make_key(provider, model_name, text)
            # Store in memory LRU
            self._memory_cache[key] = vector
            self._memory_cache.move_to_end(key)
            if len(self._memory_cache) > self._max_memory_entries:
                self._memory_cache.popitem(last=False)

            redis_mapping[key] = json.dumps(vector)

        if self._redis is not None and redis_mapping:
            try:
                pipeline = self._redis.pipeline()
                for key, val in redis_mapping.items():
                    pipeline.setex(key, self._ttl_seconds, val)
                await pipeline.execute()
            except Exception as exc:
                logger.warning("embedding_cache.redis_put_failed", error=str(exc))

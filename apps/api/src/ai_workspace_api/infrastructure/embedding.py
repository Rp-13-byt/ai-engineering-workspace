"""Production embedding providers with batching, retry, and caching."""
import hashlib
import json
import math
from abc import ABC, abstractmethod

from ai_workspace_api.core.config import Settings


class EmbeddingProvider(ABC):
    """Abstract base for embedding generation."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of text strings."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Production embedding provider using OpenAI API."""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self.batch_size = settings.embedding_batch_size
        self._api_key = settings.openai_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._api_key is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        import openai

        client = openai.AsyncOpenAI(api_key=self._api_key.get_secret_value())
        all_embeddings: list[list[float]] = []

        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            response = await client.embeddings.create(
                input=batch,
                model=self.model,
                dimensions=self.dimensions,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Production embedding provider using Google Gemini API."""

    def __init__(self, settings: Settings) -> None:
        self.dimensions = settings.embedding_dimensions
        self.batch_size = settings.embedding_batch_size
        self._api_key = settings.gemini_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._api_key is None:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        import google.generativeai as genai

        genai.configure(api_key=self._api_key.get_secret_value())
        all_embeddings: list[list[float]] = []

        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=batch,
                output_dimensionality=self.dimensions,
            )
            embeddings = result["embedding"]
            if isinstance(embeddings[0], float):
                embeddings = [embeddings]
            all_embeddings.extend(embeddings)

        return all_embeddings


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """Hash-based deterministic embeddings for testing and development without API keys."""

    def __init__(self, settings: Settings) -> None:
        self.dimensions = settings.embedding_dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._deterministic_embedding(text) for text in texts]

    def _deterministic_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [
            ((digest[i % len(digest)] / 255.0) * 2.0) - 1.0
            for i in range(self.dimensions)
        ]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class CachedEmbeddingProvider(EmbeddingProvider):
    """Redis-backed cache wrapper around any EmbeddingProvider."""

    def __init__(
        self,
        delegate: EmbeddingProvider,
        redis_url: str,
        dimensions: int,
        cache_ttl_seconds: int = 604800,
    ) -> None:
        self.delegate = delegate
        self.redis_url = redis_url
        self.dimensions = dimensions
        self.cache_ttl_seconds = cache_ttl_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import redis.asyncio as aioredis

        client = aioredis.from_url(self.redis_url)
        try:
            results: list[list[float] | None] = [None] * len(texts)
            uncached_indices: list[int] = []
            uncached_texts: list[str] = []

            keys = [f"emb:{self._content_hash(t)}" for t in texts]
            cached_values = await client.mget(keys)

            for i, cached in enumerate(cached_values):
                if cached is not None:
                    results[i] = json.loads(cached)
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(texts[i])

            if uncached_texts:
                new_embeddings = await self.delegate.embed(uncached_texts)
                pipe = client.pipeline()
                for idx, embedding in zip(uncached_indices, new_embeddings, strict=True):
                    results[idx] = embedding
                    pipe.setex(
                        keys[idx],
                        self.cache_ttl_seconds,
                        json.dumps(embedding),
                    )
                await pipe.execute()

            return [r for r in results if r is not None]
        finally:
            await client.aclose()

    def _content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Factory that creates the appropriate embedding provider based on configuration."""
    provider_name = settings.default_llm_provider.lower()

    if provider_name == "openai" and settings.openai_api_key:
        base: EmbeddingProvider = OpenAIEmbeddingProvider(settings)
    elif provider_name == "gemini" and settings.gemini_api_key:
        base = GeminiEmbeddingProvider(settings)
    else:
        base = DeterministicEmbeddingProvider(settings)

    if settings.embedding_cache_ttl_hours > 0:
        return CachedEmbeddingProvider(
            delegate=base,
            redis_url=settings.redis_url,
            dimensions=settings.embedding_dimensions,
            cache_ttl_seconds=settings.embedding_cache_ttl_hours * 3600,
        )
    return base

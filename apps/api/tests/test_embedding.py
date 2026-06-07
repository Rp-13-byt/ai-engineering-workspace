import asyncio
import math

import pytest

from ai_workspace_api.core.config import Settings
from ai_workspace_api.infrastructure.embedding import (
    CachedEmbeddingProvider,
    DeterministicEmbeddingProvider,
    create_embedding_provider,
)


def test_deterministic_provider_returns_correct_dimensions() -> None:
    settings = Settings()
    provider = DeterministicEmbeddingProvider(settings)
    result = asyncio.get_event_loop().run_until_complete(provider.embed(["hello world"]))
    assert len(result) == 1
    assert len(result[0]) == settings.embedding_dimensions


def test_deterministic_provider_is_consistent() -> None:
    settings = Settings()
    provider = DeterministicEmbeddingProvider(settings)
    loop = asyncio.get_event_loop()
    result1 = loop.run_until_complete(provider.embed(["test input"]))
    result2 = loop.run_until_complete(provider.embed(["test input"]))
    assert result1 == result2


def test_deterministic_provider_empty_input() -> None:
    settings = Settings()
    provider = DeterministicEmbeddingProvider(settings)
    result = asyncio.get_event_loop().run_until_complete(provider.embed([]))
    assert result == []


def test_deterministic_provider_normalized() -> None:
    settings = Settings()
    provider = DeterministicEmbeddingProvider(settings)
    result = asyncio.get_event_loop().run_until_complete(provider.embed(["hello"]))
    norm = math.sqrt(sum(v * v for v in result[0]))
    assert abs(norm - 1.0) < 1e-6


def test_factory_returns_deterministic_without_api_keys() -> None:
    settings = Settings(openai_api_key=None, gemini_api_key=None, embedding_cache_ttl_hours=0)
    provider = create_embedding_provider(settings)
    assert isinstance(provider, DeterministicEmbeddingProvider)


def test_factory_returns_cached_by_default() -> None:
    settings = Settings(openai_api_key=None, gemini_api_key=None)
    provider = create_embedding_provider(settings)
    assert isinstance(provider, CachedEmbeddingProvider)


def test_deterministic_provider_batch() -> None:
    settings = Settings()
    provider = DeterministicEmbeddingProvider(settings)
    texts = [f"text {i}" for i in range(10)]
    result = asyncio.get_event_loop().run_until_complete(provider.embed(texts))
    assert len(result) == 10
    for emb in result:
        assert len(emb) == settings.embedding_dimensions

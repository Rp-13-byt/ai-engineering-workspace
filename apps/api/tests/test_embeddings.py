import httpx
import pytest
from pydantic import SecretStr

from ai_workspace_api.core.config import Settings
from ai_workspace_api.infrastructure.embeddings import (
    DeterministicMockEmbeddingProvider,
    EmbeddingCache,
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    GeminiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


@pytest.mark.asyncio
async def test_deterministic_mock_provider() -> None:
    provider = DeterministicMockEmbeddingProvider(dimensions=1536)
    assert provider.name == "mock"
    assert provider.dimensions == 1536

    vectors = await provider.embed_batch(["function calculateTax()", "function calculateTax()"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1536
    # Deterministic: same text yields exact same vector
    assert vectors[0] == vectors[1]


def test_mock_provider_prohibited_in_production() -> None:
    settings = Settings(environment="production", embedding_provider="mock")
    with pytest.raises(EmbeddingConfigurationError) as exc_info:
        get_embedding_provider(settings)
    assert "prohibited in production" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dimension_validation_rejects_mismatch() -> None:
    provider = DeterministicMockEmbeddingProvider(dimensions=1536)
    with pytest.raises(EmbeddingDimensionError) as exc_info:
        provider.validate_vectors([[0.1, 0.2]])  # 2 dimensions instead of 1536
    assert "expected 1536" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_with_mock_client() -> None:
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: simulate 429 Rate Limit
            return httpx.Response(429, json={"error": "Rate limit exceeded"})
        # Second attempt: succeed with valid vector
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.05] * 1536},
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIEmbeddingProvider(
            api_key=SecretStr("test-key"),
            model_name="text-embedding-3-small",
            dimensions=1536,
            max_retries=2,
            http_client=client,
        )
        vectors = await provider.embed_batch(["def search_code(): pass"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 1536
        assert call_count == 2  # Proves retry after 429 succeeded


@pytest.mark.asyncio
async def test_gemini_provider_with_mock_client() -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert "models/text-embedding-004:batchEmbedContents" in str(request.url)
        return httpx.Response(
            200,
            json={
                "embeddings": [
                    {"values": [0.1] * 768},
                ]
            },
        )

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiEmbeddingProvider(
            api_key=SecretStr("test-key"),
            model_name="models/text-embedding-004",
            dimensions=768,
            http_client=client,
        )
        vectors = await provider.embed_batch(["class SearchEngine: pass"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 768


@pytest.mark.asyncio
async def test_embedding_cache_composite_key_and_lru() -> None:
    cache = EmbeddingCache(redis=None, max_memory_entries=2)
    key1 = cache.make_key("openai", "text-embedding-3-small", "code snippet 1")
    key_other_model = cache.make_key("openai", "text-embedding-3-large", "code snippet 1")

    # Composite key must differentiate models even for identical text
    assert key1 != key_other_model

    # Populate cache
    await cache.put_many("openai", "text-embedding-3-small", [(0, "code snippet 1", [0.1, 0.2])])

    hits, misses = await cache.get_many(
        "openai",
        "text-embedding-3-small",
        ["code snippet 1", "code snippet 2"],
    )
    assert 0 in hits
    assert hits[0] == [0.1, 0.2]
    assert len(misses) == 1
    assert misses[0] == (1, "code snippet 2")

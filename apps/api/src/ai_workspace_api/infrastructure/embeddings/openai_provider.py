import asyncio
from typing import Any, cast

import httpx
from pydantic import SecretStr

from ai_workspace_api.core.logging import get_logger
from ai_workspace_api.infrastructure.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
)

logger = get_logger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Production OpenAI embedding provider supporting text-embedding-3-small/large."""

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str = "text-embedding-3-small",
        dimensions: int = 1536,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = http_client

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "input": texts,
            "model": self._model_name,
        }
        # text-embedding-3 supports dimensions parameter
        if "text-embedding-3" in self._model_name:
            payload["dimensions"] = self._dimensions

        response_data = await self._send_with_retry(url, headers, payload)
        items = response_data.get("data", [])
        # OpenAI returns items with an "index" field; sort to preserve order
        items_sorted = sorted(items, key=lambda item: item.get("index", 0))
        vectors = [item["embedding"] for item in items_sorted]

        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                f"OpenAI returned {len(vectors)} embeddings for {len(texts)} input texts"
            )

        self.validate_vectors(vectors)
        return vectors

    async def _send_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        backoff = 0.5
        for attempt in range(self._max_retries + 1):
            try:
                client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
                try:
                    response = await client.post(url, json=payload, headers=headers)
                finally:
                    if self._client is None:
                        await client.aclose()

                if response.status_code == 200:
                    return cast(dict[str, Any], response.json())

                if response.status_code == 429:
                    if attempt < self._max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    raise EmbeddingRateLimitError(
                        f"OpenAI API rate limit exceeded: {response.text}"
                    )

                if response.status_code in (500, 502, 503, 504):
                    if attempt < self._max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                raise EmbeddingProviderError(
                    f"OpenAI API returned HTTP {response.status_code}: {response.text}"
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                raise EmbeddingProviderError(
                    f"OpenAI API request failed after {self._max_retries} retries: {exc}"
                ) from exc

        raise EmbeddingProviderError("OpenAI API call failed unexpectedly")

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


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Production Gemini embedding provider using Google Generative AI REST API."""

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str = "models/text-embedding-004",
        dimensions: int = 768,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        # Ensure model is formatted with prefix if not present
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        self._model_name = model_name
        self._dimensions = dimensions
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = http_client

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/{self._model_name}:batchEmbedContents"
            f"?key={self._api_key.get_secret_value()}"
        )
        headers = {"Content-Type": "application/json"}
        requests = [
            {
                "model": self._model_name,
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self._dimensions,
            }
            for text in texts
        ]
        payload = {"requests": requests}

        response_data = await self._send_with_retry(url, headers, payload)
        embeddings = response_data.get("embeddings", [])
        vectors = [item.get("values", []) for item in embeddings]

        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                f"Gemini returned {len(vectors)} embeddings for {len(texts)} input texts"
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
                        f"Gemini API rate limit exceeded: {response.text}"
                    )

                if response.status_code in (500, 502, 503, 504):
                    if attempt < self._max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue

                raise EmbeddingProviderError(
                    f"Gemini API returned HTTP {response.status_code}: {response.text}"
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                raise EmbeddingProviderError(
                    f"Gemini API request failed after {self._max_retries} retries: {exc}"
                ) from exc

        raise EmbeddingProviderError("Gemini API call failed unexpectedly")

import hashlib
import math

from ai_workspace_api.infrastructure.embeddings.base import EmbeddingProvider


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock provider using normalized SHA-256 digests.

    Used strictly for testing and offline local development.
    """

    def __init__(self, model_name: str = "mock-embedding", dimensions: int = 1536) -> None:
        self._model_name = model_name
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results = [self._embed_single(text) for text in texts]
        self.validate_vectors(results)
        return results

    def _embed_single(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [
            ((digest[i % len(digest)] / 255.0) * 2.0) - 1.0
            for i in range(self._dimensions)
        ]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

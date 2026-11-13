from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""


class EmbeddingProviderError(EmbeddingError):
    """Raised when an external embedding provider fails or returns an error."""


class EmbeddingDimensionError(EmbeddingError):
    """Raised when the generated embedding vector does not match the expected dimensions."""


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Raised when an embedding provider rate limits requests (HTTP 429)."""


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when embedding provider configuration is missing, invalid, or disallowed."""


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'openai', 'gemini', 'mock')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the model (e.g. 'text-embedding-3-small')."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Expected dimension size of returned vectors."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts without caching."""

    def validate_vectors(self, vectors: list[list[float]]) -> None:
        """Validate that all returned vectors match expected dimension size."""
        for idx, vec in enumerate(vectors):
            if len(vec) != self.dimensions:
                raise EmbeddingDimensionError(
                    f"Vector at index {idx} has dimension {len(vec)}, "
                    f"expected {self.dimensions} for model '{self.model_name}'"
                )

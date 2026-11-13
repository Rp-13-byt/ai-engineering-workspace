from ai_workspace_api.core.config import Settings
from ai_workspace_api.infrastructure.embeddings.base import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
)
from ai_workspace_api.infrastructure.embeddings.gemini_provider import (
    GeminiEmbeddingProvider,
)
from ai_workspace_api.infrastructure.embeddings.mock_provider import (
    DeterministicMockEmbeddingProvider,
)
from ai_workspace_api.infrastructure.embeddings.openai_provider import (
    OpenAIEmbeddingProvider,
)


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider_name = settings.embedding_provider.lower().strip()

    if settings.is_production() and provider_name == "mock":
        raise EmbeddingConfigurationError(
            "Deterministic mock embedding provider is prohibited in production environments. "
            "Configure 'openai' or 'gemini' with a valid API key."
        )

    if provider_name == "openai":
        if not settings.openai_api_key or not settings.openai_api_key.get_secret_value():
            if settings.is_production():
                raise EmbeddingConfigurationError(
                    "OPENAI_API_KEY must be configured when embedding_provider is 'openai'"
                )
            raise EmbeddingConfigurationError(
                "OPENAI_API_KEY is not configured. Provide OPENAI_API_KEY "
                "or set EMBEDDING_PROVIDER=mock for local dev."
            )
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model_name=settings.embedding_model or "text-embedding-3-small",
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
        )

    if provider_name == "gemini":
        if not settings.gemini_api_key or not settings.gemini_api_key.get_secret_value():
            if settings.is_production():
                raise EmbeddingConfigurationError(
                    "GEMINI_API_KEY must be configured when embedding_provider is 'gemini'"
                )
            raise EmbeddingConfigurationError(
                "GEMINI_API_KEY is not configured. Provide GEMINI_API_KEY "
                "or set EMBEDDING_PROVIDER=mock for local dev."
            )
        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.embedding_model or "models/text-embedding-004",
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
        )

    if provider_name == "mock":
        return DeterministicMockEmbeddingProvider(
            model_name=settings.embedding_model or "mock-embedding-v1",
            dimensions=settings.embedding_dimensions,
        )

    raise EmbeddingConfigurationError(
        f"Unsupported embedding provider: '{provider_name}'. "
        "Supported providers: 'openai', 'gemini', 'mock'"
    )

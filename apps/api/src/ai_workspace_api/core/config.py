from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"
    public_app_url: AnyHttpUrl | str = "http://localhost:3000"
    api_base_url: AnyHttpUrl | str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://workspace:workspace@localhost:5432/workspace"
    sync_database_url: str = "postgresql://workspace:workspace@localhost:5432/workspace"
    database_pool_size: int = 20
    database_max_overflow: int = 20

    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://workspace:workspace@localhost:5672/"

    jwt_secret: SecretStr = Field(default=SecretStr("change-me-in-production"))
    jwt_issuer: str = "ai-workspace"
    jwt_audience: str = "ai-workspace-web"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    github_client_id: str = ""
    github_client_secret: SecretStr | None = None
    github_webhook_secret: SecretStr | None = None

    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    default_llm_provider: str = "openai"
    embedding_dimensions: int = 1536
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 96
    embedding_cache_ttl_hours: int = 168

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "workspace"
    s3_secret_access_key: SecretStr = Field(default=SecretStr("workspace-secret"))
    s3_bucket: str = "ai-workspace-artifacts"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_per_minute: int = 120

    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

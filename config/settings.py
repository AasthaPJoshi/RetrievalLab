# =============================================================================
# RetrievalLab — config/settings.py
# =============================================================================
# PURPOSE : Central application configuration using Pydantic Settings v2.
#           Reads from environment variables (or .env file) and validates
#           types + constraints at startup — fail fast, never fail silently.
#
# DESIGN DECISIONS:
#   • All settings are typed — no raw os.getenv() scattered across the codebase.
#   • Nested models group related config (DatabaseSettings, RedisSettings, etc.)
#   • Sensitive values (API keys) use SecretStr so they never appear in logs.
#   • A single `get_settings()` function with LRU cache ensures the .env file
#     is read exactly once per process lifecycle.
#
# USAGE:
#   from config.settings import get_settings
#   settings = get_settings()
#   db_url = settings.database.url        # fully typed, validated
#   api_key = settings.llm.anthropic_api_key.get_secret_value()
#
# INPUT  : Environment variables or .env file in project root
# OUTPUT : Validated Settings object; raises ValidationError on bad config
# =============================================================================

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ─── Sub-models ──────────────────────────────────────────────────────────────

class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host:     str = "localhost"
    port:     int = 5432
    db:       str = "retrievallab"
    user:     str = "retrievallab"
    password: SecretStr = Field(default=SecretStr("retrievallab_dev_password"))

    @property
    def url(self) -> str:
        """Async SQLAlchemy connection URL."""
        pw = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pw}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        """Sync URL for Alembic migrations."""
        pw = self.password.get_secret_value()
        return f"postgresql+psycopg2://{self.user}:{pw}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host:     str = "localhost"
    port:     int = 6379
    password: SecretStr | None = None

    @property
    def url(self) -> str:
        if self.password:
            pw = self.password.get_secret_value()
            return f"redis://:{pw}@{self.host}:{self.port}/0"
        return f"redis://{self.host}:{self.port}/0"

    @property
    def celery_broker_url(self) -> str:
        base = self.url.replace("/0", "/1")  # Celery broker on DB 1
        return base

    @property
    def celery_result_backend(self) -> str:
        base = self.url.replace("/0", "/2")  # Celery results on DB 2
        return base


class MinIOSettings(BaseSettings):
    """MinIO / S3 object storage settings."""

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint:    str        = "localhost:9000"
    access_key:  SecretStr  = Field(default=SecretStr("minioadmin"))
    secret_key:  SecretStr  = Field(default=SecretStr("minioadmin"))
    bucket_name: str        = "retrievallab"
    secure:      bool       = False


class ChromaSettings(BaseSettings):
    """ChromaDB settings."""

    model_config = SettingsConfigDict(env_prefix="CHROMA_")

    host:              str = "localhost"
    port:              int = 8001
    collection_prefix: str = "rl_"

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class ElasticsearchSettings(BaseSettings):
    """Elasticsearch settings."""

    model_config = SettingsConfigDict(env_prefix="ELASTICSEARCH_")

    url:          str = "http://localhost:9200"
    index_prefix: str = "rl_"


class LLMSettings(BaseSettings):
    """LLM provider API keys and default models."""

    model_config = SettingsConfigDict(env_prefix="")

    # API Keys — stored as SecretStr to prevent accidental logging
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key:    SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    cohere_api_key:    SecretStr | None = Field(default=None, alias="COHERE_API_KEY")

    # Default models
    default_chat_model:  str = Field(default="claude-3-5-haiku-20241022", alias="DEFAULT_CHAT_MODEL")
    default_embed_model: str = Field(default="text-embedding-3-small",    alias="DEFAULT_EMBED_MODEL")
    default_provider:    str = Field(default="anthropic",                 alias="DEFAULT_LLM_PROVIDER")

    model_config = SettingsConfigDict(populate_by_name=True)


class ChunkingSettings(BaseSettings):
    """Default chunking configuration."""

    model_config = SettingsConfigDict(env_prefix="DEFAULT_CHUNK_")

    size:     int = Field(default=512,       alias="DEFAULT_CHUNK_SIZE")
    overlap:  int = Field(default=64,        alias="DEFAULT_CHUNK_OVERLAP")
    strategy: str = Field(default="recursive", alias="DEFAULT_CHUNK_STRATEGY")

    model_config = SettingsConfigDict(populate_by_name=True)

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid = {
            "fixed", "recursive", "semantic", "sentence_window",
            "raptor", "propositional", "document_structure",
            "late", "code_aware", "table_aware",
        }
        if v not in valid:
            raise ValueError(f"chunk strategy must be one of: {valid}")
        return v


class RetrievalSettings(BaseSettings):
    """Default retrieval configuration."""

    model_config = SettingsConfigDict(populate_by_name=True)

    top_k:     int = Field(default=10,      alias="DEFAULT_TOP_K")
    retriever: str = Field(default="hybrid", alias="DEFAULT_RETRIEVER")

    @field_validator("retriever")
    @classmethod
    def validate_retriever(cls, v: str) -> str:
        valid = {"sparse", "dense", "hybrid", "agentic"}
        if v not in valid:
            raise ValueError(f"retriever must be one of: {valid}")
        return v


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry and Prometheus settings."""

    model_config = SettingsConfigDict(populate_by_name=True)

    otel_endpoint:    str  = Field(default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_service_name: str = Field(default="retrievallab-api",     alias="OTEL_SERVICE_NAME")
    prometheus_port:  int  = Field(default=9090,                   alias="PROMETHEUS_PORT")


class MLflowSettings(BaseSettings):
    """MLflow experiment tracking settings."""

    model_config = SettingsConfigDict(populate_by_name=True)

    tracking_uri:    str = Field(default="http://localhost:5000",    alias="MLFLOW_TRACKING_URI")
    experiment_name: str = Field(default="retrievallab_default",     alias="MLFLOW_EXPERIMENT_NAME")


# ─── Root Settings ───────────────────────────────────────────────────────────

class Settings(BaseSettings):
    """
    Root application settings.

    All sub-models are loaded from environment variables or .env file.
    Pydantic validates types and constraints at import time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",           # ignore unknown env vars silently
    )

    # App identity
    app_name:  str     = "RetrievalLab"
    app_env:   Literal["development", "staging", "production"] = "development"
    app_debug: bool    = True
    app_host:  str     = "0.0.0.0"
    app_port:  int     = 8000
    secret_key: SecretStr = Field(default=SecretStr("change_me_in_production_32chars"))

    # Logging
    log_level:  str = "INFO"
    log_format: Literal["json", "pretty"] = "pretty"

    # Embedding cache
    embed_cache_ttl_seconds: int = 86400
    embed_cache_max_size_mb: int = 500

    # Sub-models (each reads from its own env prefix)
    database:      DatabaseSettings      = DatabaseSettings()
    redis:         RedisSettings         = RedisSettings()
    minio:         MinIOSettings         = MinIOSettings()
    chroma:        ChromaSettings        = ChromaSettings()
    elasticsearch: ElasticsearchSettings = ElasticsearchSettings()
    llm:           LLMSettings           = LLMSettings()
    chunking:      ChunkingSettings      = ChunkingSettings()
    retrieval:     RetrievalSettings     = RetrievalSettings()
    observability: ObservabilitySettings = ObservabilitySettings()
    mlflow:        MLflowSettings        = MLflowSettings()

    @model_validator(mode="after")
    def warn_missing_api_keys(self) -> "Settings":
        """Warn (not error) if no LLM API keys are configured."""
        if (
            self.llm.anthropic_api_key is None
            and self.llm.openai_api_key is None
        ):
            import warnings
            warnings.warn(
                "No LLM API keys configured. "
                "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env for full functionality.",
                stacklevel=2,
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


# ─── Cached accessor ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Using @lru_cache ensures:
    1. .env is read exactly once per process.
    2. All parts of the codebase share the same config object.
    3. Tests can override via get_settings.cache_clear() + monkeypatching.

    Returns:
        Validated Settings object.

    Raises:
        pydantic.ValidationError: If required settings are missing or invalid.
    """
    return Settings()

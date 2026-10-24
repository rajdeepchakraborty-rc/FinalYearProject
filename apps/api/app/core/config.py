"""
SignalStream — Application Configuration
==========================================
Pydantic Settings for type-safe environment variable loading.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # General
    APP_NAME: str = "signalstream"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str = "change-me-in-production"

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_CORS_ORIGINS: str = "http://localhost:3000"
    API_RATE_LIMIT_PER_MINUTE: int = 1000
    API_MAX_REQUEST_SIZE_MB: int = 10

    # JWT
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://signalstream:signalstream@localhost:5432/signalstream"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 100

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"
    KAFKA_COMPRESSION_TYPE: str = "lz4"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "signalstream"
    S3_REGION: str = "us-east-1"

    # Inference
    INFERENCE_SERVER_URL: str = "http://localhost:8100"
    INFERENCE_TIMEOUT_SECONDS: int = 30

    # MCP
    MCP_SERVER_URL: str = "http://localhost:8200"
    MCP_TIMEOUT_SECONDS: int = 5

    # LLM
    LLM_DEFAULT_PROVIDER: str = "openai"
    LLM_FALLBACK_PROVIDER: str = "anthropic"
    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TIMEOUT_SECONDS: int = 60
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_DEFAULT_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MAX_TOKENS: int = 4096
    LOCAL_LLM_URL: str = "http://localhost:8300"
    LOCAL_LLM_MODEL: str = "llama3"

    # LLM Cost Control
    LLM_DAILY_TOKEN_BUDGET: int = 1000000
    LLM_CACHE_TTL_SECONDS: int = 1800
    LLM_SEMANTIC_CACHE_THRESHOLD: float = 0.95

    # Monitoring
    SENTRY_DSN: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # PII
    PII_DETECTION_ENABLED: bool = True
    PII_REDACTION_ENABLED: bool = True

    # Auto Resolver
    AUTO_RESOLVE_CONFIDENCE_THRESHOLD: float = 0.95
    DRAFT_RESPONSE_CONFIDENCE_THRESHOLD: float = 0.75
    HIGH_RISK_CATEGORIES: str = "fraud,legal,security,safety,regulatory"

    # Data Retention
    RETENTION_RAW_EVENTS_DAYS: int = 90
    RETENTION_ANALYTICS_DAYS: int = 1095
    RETENTION_AUDIT_LOGS_DAYS: int = 365
    RETENTION_EMBEDDINGS_DAYS: int = 365

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.API_CORS_ORIGINS.split(",")]

    @property
    def high_risk_categories_list(self) -> list[str]:
        return [c.strip() for c in self.HIGH_RISK_CATEGORIES.split(",")]

    model_config = {"env_file": ".env", "case_sensitive": True}


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

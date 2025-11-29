"""Core configuration for Analytics Engine."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )

    # Database
    database_url: str = "postgresql+asyncpg://dev:dev123@localhost:5432/analytics_dev"
    database_url_sync: str = "postgresql://dev:dev123@localhost:5432/analytics_dev"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # Service
    service_name: str = "analytics-engine"
    service_version: str = "0.1.0"

    # Logging
    log_level: str = "INFO"
    debug: bool = False

    # PhoBERT Model
    phobert_model_path: str = "infrastructure/phobert/models"
    phobert_max_length: int = 128
    phobert_model_file: str = "model_quantized.onnx"

    # MinIO (for model artifacts)
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"


settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings

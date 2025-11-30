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

    # SpaCy-YAKE Keyword Extraction
    spacy_model: str = "xx_ent_wiki_sm"  # Multilingual model (recommended for Vietnamese)
    yake_language: str = "vi"  # Vietnamese language code
    yake_n: int = 2
    yake_dedup_lim: float = 0.8
    yake_max_keywords: int = 30
    max_keywords: int = 30
    entity_weight: float = 0.7
    chunk_weight: float = 0.5

    # Aspect Mapping
    enable_aspect_mapping: bool = False
    aspect_dictionary_path: str = "config/aspects.yaml"
    unknown_aspect_label: str = "UNKNOWN"

    # RabbitMQ (for message queue)
    rabbitmq_url: str = "amqp://guest:guest@localhost/"
    rabbitmq_queue_name: str = "analytics_queue"
    rabbitmq_prefetch_count: int = 1

    # MinIO (for model artifacts)
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"

    # Text Preprocessor
    preprocessor_min_text_length: int = 10
    preprocessor_max_comments: int = 5

    # Intent Classifier
    intent_classifier_enabled: bool = True
    intent_classifier_confidence_threshold: float = 0.5
    intent_patterns_path: str = "config/intent_patterns.yaml"


settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings

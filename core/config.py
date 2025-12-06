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

    # Compression settings
    compression_enabled: bool = True
    compression_default_level: int = 2
    compression_algorithm: str = "zstd"
    compression_min_size_bytes: int = 1024

    # Text Preprocessor
    preprocessor_min_text_length: int = 10
    preprocessor_max_comments: int = 5

    # Intent Classifier
    intent_classifier_enabled: bool = True
    intent_classifier_confidence_threshold: float = 0.5
    intent_patterns_path: str = "config/intent_patterns.yaml"

    # Impact & Risk Calculator (Module 5)
    # Interaction weights (EngagementScore)
    impact_weight_view: float = 0.01
    impact_weight_like: float = 1.0
    impact_weight_comment: float = 2.0
    impact_weight_save: float = 3.0
    impact_weight_share: float = 5.0

    # Platform multipliers
    impact_platform_weight_tiktok: float = 1.0
    impact_platform_weight_facebook: float = 1.2
    impact_platform_weight_youtube: float = 1.5
    impact_platform_weight_instagram: float = 1.1
    impact_platform_weight_unknown: float = 1.0

    # Sentiment amplifiers
    impact_amp_negative: float = 1.5
    impact_amp_neutral: float = 1.0
    impact_amp_positive: float = 1.1

    # Thresholds
    impact_viral_threshold: float = 70.0
    impact_kol_follower_threshold: int = 50000
    impact_max_raw_score_ceiling: float = 100000.0

    # Event Queue Settings
    event_exchange: str = "smap.events"
    event_routing_key: str = "data.collected"
    event_queue_name: str = "analytics.data.collected"

    # Batch Processing Settings
    max_concurrent_batches: int = 5
    batch_timeout_seconds: int = 30
    expected_batch_size_tiktok: int = 50
    expected_batch_size_youtube: int = 20

    # MinIO Crawl Results Settings
    minio_crawl_results_bucket: str = "crawl-results"

    # Error Handling Settings
    max_retries_per_item: int = 3
    error_backoff_base_seconds: float = 1.0
    error_backoff_max_seconds: float = 60.0

    # Metrics Settings
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # Database Pool Settings (for batch processing)
    database_pool_size: int = 20
    database_max_overflow: int = 10


settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings

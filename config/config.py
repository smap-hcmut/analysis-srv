import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv


@dataclass
class ServiceConfig:
    """Service information."""

    name: str = "analytics-engine"
    version: str = "0.1.0"
    environment: str = "development"


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str = "postgresql+asyncpg://dev:dev123@localhost:5432/analytics_dev"
    url_sync: str = "postgresql://dev:dev123@localhost:5432/analytics_dev"
    schema: str = "schema_analyst"
    pool_size: int = 20
    max_overflow: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    debug: bool = False
    enable_console: bool = True
    colorize: bool = True
    service_name: str = "analytics-engine"


@dataclass
class PhoBERTConfig:
    """PhoBERT model configuration."""

    model_path: str = "internal/model/phobert_sentiment"
    max_length: int = 256


@dataclass
class KeywordExtractionConfig:
    """Keyword extraction configuration."""

    spacy_model: str = "xx_ent_wiki_sm"
    yake_language: str = "vi"
    yake_n: int = 2
    yake_dedup_lim: float = 0.8
    yake_max_keywords: int = 30
    max_keywords: int = 30
    entity_weight: float = 0.7
    chunk_weight: float = 0.5


@dataclass
class AspectMappingConfig:
    """Aspect mapping configuration."""

    enabled: bool = False
    dictionary_path: str = "config/aspects.yaml"
    unknown_label: str = "UNKNOWN"


@dataclass
class RabbitMQEventConfig:
    """RabbitMQ event queue configuration."""

    exchange: str = "smap.events"
    routing_key: str = "data.collected"
    queue_name: str = "analytics.data.collected"


@dataclass
class RabbitMQPublishConfig:
    """RabbitMQ publish configuration."""

    exchange: str = "results.inbound"
    routing_key: str = "analyze.result"
    enabled: bool = True


@dataclass
class RabbitMQConfig:
    """RabbitMQ configuration."""

    url: str = "amqp://guest:guest@localhost/"
    queue_name: str = "analytics_queue"
    prefetch_count: int = 1
    event: RabbitMQEventConfig = field(default_factory=RabbitMQEventConfig)
    publish: RabbitMQPublishConfig = field(default_factory=RabbitMQPublishConfig)


@dataclass
class RedisConfig:
    """Redis configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 50


@dataclass
class MinIOConfig:
    """MinIO configuration."""

    endpoint: str = "172.16.21.10:9000"
    access_key: str = "tantai"
    secret_key: str = "21042004"
    secure: bool = False
    crawl_results_bucket: str = "crawl-results"


@dataclass
class CompressionConfig:
    """Compression configuration."""

    enabled: bool = True
    default_level: int = 2
    algorithm: str = "zstd"
    min_size_bytes: int = 1024


@dataclass
class PreprocessorConfig:
    """Text preprocessor configuration."""

    min_text_length: int = 10
    max_comments: int = 5


@dataclass
class IntentClassifierConfig:
    """Intent classifier configuration."""

    enabled: bool = True
    confidence_threshold: float = 0.5
    patterns_path: str = "config/intent_patterns.yaml"


@dataclass
class ImpactWeightConfig:
    """Impact calculation weights."""

    view: float = 0.01
    like: float = 1.0
    comment: float = 2.0
    save: float = 3.0
    share: float = 5.0


@dataclass
class ImpactPlatformConfig:
    """Impact platform multipliers."""

    tiktok: float = 1.0
    facebook: float = 1.2
    youtube: float = 1.5
    instagram: float = 1.1
    unknown: float = 1.0


@dataclass
class ImpactAmplifierConfig:
    """Impact sentiment amplifiers."""

    negative: float = 1.5
    neutral: float = 1.0
    positive: float = 1.1


@dataclass
class ImpactThresholdConfig:
    """Impact thresholds."""

    viral: float = 70.0
    kol_followers: int = 50000
    max_raw_score: float = 100000.0


@dataclass
class ImpactConfig:
    """Impact & risk calculator configuration."""

    weight: ImpactWeightConfig = field(default_factory=ImpactWeightConfig)
    platform: ImpactPlatformConfig = field(default_factory=ImpactPlatformConfig)
    amplifier: ImpactAmplifierConfig = field(default_factory=ImpactAmplifierConfig)
    threshold: ImpactThresholdConfig = field(default_factory=ImpactThresholdConfig)


@dataclass
class BatchExpectedSizeConfig:
    """Expected batch sizes per platform."""

    tiktok: int = 50
    youtube: int = 20


@dataclass
class BatchConfig:
    """Batch processing configuration."""

    max_concurrent: int = 5
    timeout_seconds: int = 30
    expected_size: BatchExpectedSizeConfig = field(
        default_factory=BatchExpectedSizeConfig
    )


@dataclass
class ErrorConfig:
    """Error handling configuration."""

    max_retries_per_item: int = 3
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 60.0


@dataclass
class DebugConfig:
    """Debug monitoring configuration."""

    raw_data: str = "false"
    sample_rate: int = 100


@dataclass
class APIConfig:
    """API service configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    root_path: str = ""


@dataclass
class Config:
    """Main configuration container.

    This is the root config object that contains all sub-configurations.
    Similar to Go's Viper config struct.
    """

    service: ServiceConfig = field(default_factory=ServiceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    phobert: PhoBERTConfig = field(default_factory=PhoBERTConfig)
    keyword_extraction: KeywordExtractionConfig = field(
        default_factory=KeywordExtractionConfig
    )
    aspect_mapping: AspectMappingConfig = field(default_factory=AspectMappingConfig)
    rabbitmq: RabbitMQConfig = field(default_factory=RabbitMQConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    minio: MinIOConfig = field(default_factory=MinIOConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    preprocessor: PreprocessorConfig = field(default_factory=PreprocessorConfig)
    intent_classifier: IntentClassifierConfig = field(
        default_factory=IntentClassifierConfig
    )
    impact: ImpactConfig = field(default_factory=ImpactConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    error: ErrorConfig = field(default_factory=ErrorConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    api: APIConfig = field(default_factory=APIConfig)


class ConfigLoader:
    """Viper-style configuration loader.

    Loads configuration from:
    1. YAML files (lowest priority)
    2. .env files
    3. Environment variables (highest priority)
    """

    def __init__(self):
        self.config_name = "config"
        self.config_type = "yaml"
        self.config_paths = [".", "config", "/etc/analytics"]
        self.env_prefix = "ANALYTICS"
        self.auto_env = True
        self._raw_config: Dict[str, Any] = {}

    def set_config_name(self, name: str) -> None:
        """Set config file name (without extension)."""
        self.config_name = name

    def add_config_path(self, path: str) -> None:
        """Add path to search for config files."""
        if path not in self.config_paths:
            self.config_paths.append(path)

    def set_env_prefix(self, prefix: str) -> None:
        """Set environment variable prefix."""
        self.env_prefix = prefix.upper()

    def read_config(self) -> Config:
        """Read configuration from all sources.

        Returns:
            Config object with all settings
        """
        # Step 1: Load YAML config
        self._load_yaml()

        # Step 2: Load .env files
        self._load_env_files()

        # Step 3: Build Config object with env overrides
        config = self._build_config()

        # Step 4: Validate configuration
        self._validate(config)

        return config

    def _load_yaml(self) -> None:
        """Load YAML configuration file."""
        config_file = None

        # Search for config file
        for path in self.config_paths:
            for ext in ["yaml", "yml"]:
                file_path = Path(path) / f"{self.config_name}.{ext}"
                if file_path.exists():
                    config_file = file_path
                    break
            if config_file:
                break

        if not config_file:
            return

        # Load YAML
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self._raw_config = yaml.safe_load(f) or {}
        except Exception as e:
            raise

    def _load_env_files(self) -> None:
        """Load .env files."""
        for env_file in [".env", ".env.local"]:
            for path in self.config_paths:
                env_path = Path(path) / env_file
                if env_path.exists():
                    load_dotenv(env_path, override=True)

    def _get_env(self, key: str, default: Any = None) -> Any:
        """Get value from environment variable.

        Converts nested key to env var:
        - "database.url" -> "ANALYTICS_DATABASE_URL"
        """
        if not self.auto_env:
            return default

        env_key = key.replace(".", "_").upper()
        if self.env_prefix:
            env_key = f"{self.env_prefix}_{env_key}"

        return os.getenv(env_key, default)

    def _get_value(self, key: str, default: Any = None) -> Any:
        """Get value with priority: env > yaml > default."""
        # Check environment variable first
        env_value = self._get_env(key)
        if env_value is not None:
            # Automatic type conversion for bool, int, float, list from env if possible
            default_type = type(default)
            value = env_value
            if default_type == bool:
                return env_value.lower() in ("true", "1", "yes")
            elif default_type == int:
                try:
                    return int(env_value)
                except Exception:
                    return default
            elif default_type == float:
                try:
                    return float(env_value)
                except Exception:
                    return default
            elif default_type == list:
                try:
                    # Interpret comma-separated env variables as list
                    return [item.strip() for item in env_value.split(",")]
                except Exception:
                    return default
            else:
                return env_value

        # Check YAML config
        keys = key.split(".")
        value = self._raw_config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def _build_config(self) -> Config:
        """Build Config object from loaded values."""
        return Config(
            service=ServiceConfig(
                name=self._get_value("service.name", "analytics-engine"),
                version=self._get_value("service.version", "0.1.0"),
                environment=self._get_value("service.environment", "development"),
            ),
            database=DatabaseConfig(
                url=self._get_value(
                    "database.url",
                    "postgresql+asyncpg://dev:dev123@localhost:5432/analytics_dev",
                ),
                url_sync=self._get_value(
                    "database.url_sync",
                    "postgresql://dev:dev123@localhost:5432/analytics_dev",
                ),
                schema=self._get_value("database.schema", "schema_analyst"),
                pool_size=self._get_value("database.pool_size", 20),
                max_overflow=self._get_value("database.max_overflow", 10),
            ),
            logging=LoggingConfig(
                level=self._get_value("logging.level", "INFO"),
                debug=self._get_value("logging.debug", False),
                enable_console=self._get_value("logging.enable_console", True),
                colorize=self._get_value("logging.colorize", True),
                service_name=self._get_value(
                    "logging.service_name", "analytics-engine"
                ),
            ),
            phobert=PhoBERTConfig(
                model_path=self._get_value(
                    "phobert.model_path", "internal/model/phobert_sentiment"
                ),
                max_length=self._get_value("phobert.max_length", 256),
            ),
            keyword_extraction=KeywordExtractionConfig(
                spacy_model=self._get_value(
                    "keyword_extraction.spacy_model", "xx_ent_wiki_sm"
                ),
                yake_language=self._get_value("keyword_extraction.yake_language", "vi"),
                yake_n=self._get_value("keyword_extraction.yake_n", 2),
                yake_dedup_lim=self._get_value(
                    "keyword_extraction.yake_dedup_lim", 0.8
                ),
                yake_max_keywords=self._get_value(
                    "keyword_extraction.yake_max_keywords", 30
                ),
                max_keywords=self._get_value("keyword_extraction.max_keywords", 30),
                entity_weight=self._get_value("keyword_extraction.entity_weight", 0.7),
                chunk_weight=self._get_value("keyword_extraction.chunk_weight", 0.5),
            ),
            aspect_mapping=AspectMappingConfig(
                enabled=self._get_value("aspect_mapping.enabled", False),
                dictionary_path=self._get_value(
                    "aspect_mapping.dictionary_path", "config/aspects.yaml"
                ),
                unknown_label=self._get_value(
                    "aspect_mapping.unknown_label", "UNKNOWN"
                ),
            ),
            rabbitmq=RabbitMQConfig(
                url=self._get_value("rabbitmq.url", "amqp://guest:guest@localhost/"),
                queue_name=self._get_value("rabbitmq.queue_name", "analytics_queue"),
                prefetch_count=self._get_value("rabbitmq.prefetch_count", 1),
                event=RabbitMQEventConfig(
                    exchange=self._get_value("rabbitmq.event.exchange", "smap.events"),
                    routing_key=self._get_value(
                        "rabbitmq.event.routing_key", "data.collected"
                    ),
                    queue_name=self._get_value(
                        "rabbitmq.event.queue_name", "analytics.data.collected"
                    ),
                ),
                publish=RabbitMQPublishConfig(
                    exchange=self._get_value(
                        "rabbitmq.publish.exchange", "results.inbound"
                    ),
                    routing_key=self._get_value(
                        "rabbitmq.publish.routing_key", "analyze.result"
                    ),
                    enabled=self._get_value("rabbitmq.publish.enabled", True),
                ),
            ),
            redis=RedisConfig(
                host=self._get_value("redis.host", "localhost"),
                port=self._get_value("redis.port", 6379),
                db=self._get_value("redis.db", 0),
                password=self._get_value("redis.password", None),
                max_connections=self._get_value("redis.max_connections", 50),
            ),
            minio=MinIOConfig(
                endpoint=self._get_value("minio.endpoint", "172.16.21.10:9000"),
                access_key=self._get_value("minio.access_key", "tantai"),
                secret_key=self._get_value("minio.secret_key", "21042004"),
                secure=self._get_value("minio.secure", False),
                crawl_results_bucket=self._get_value(
                    "minio.crawl_results_bucket", "crawl-results"
                ),
            ),
            compression=CompressionConfig(
                enabled=self._get_value("compression.enabled", True),
                default_level=self._get_value("compression.default_level", 2),
                algorithm=self._get_value("compression.algorithm", "zstd"),
                min_size_bytes=self._get_value("compression.min_size_bytes", 1024),
            ),
            preprocessor=PreprocessorConfig(
                min_text_length=self._get_value("preprocessor.min_text_length", 10),
                max_comments=self._get_value("preprocessor.max_comments", 5),
            ),
            intent_classifier=IntentClassifierConfig(
                enabled=self._get_value("intent_classifier.enabled", True),
                confidence_threshold=self._get_value(
                    "intent_classifier.confidence_threshold", 0.5
                ),
                patterns_path=self._get_value(
                    "intent_classifier.patterns_path", "config/intent_patterns.yaml"
                ),
            ),
            impact=ImpactConfig(
                weight=ImpactWeightConfig(
                    view=self._get_value("impact.weight.view", 0.01),
                    like=self._get_value("impact.weight.like", 1.0),
                    comment=self._get_value("impact.weight.comment", 2.0),
                    save=self._get_value("impact.weight.save", 3.0),
                    share=self._get_value("impact.weight.share", 5.0),
                ),
                platform=ImpactPlatformConfig(
                    tiktok=self._get_value("impact.platform.tiktok", 1.0),
                    facebook=self._get_value("impact.platform.facebook", 1.2),
                    youtube=self._get_value("impact.platform.youtube", 1.5),
                    instagram=self._get_value("impact.platform.instagram", 1.1),
                    unknown=self._get_value("impact.platform.unknown", 1.0),
                ),
                amplifier=ImpactAmplifierConfig(
                    negative=self._get_value("impact.amplifier.negative", 1.5),
                    neutral=self._get_value("impact.amplifier.neutral", 1.0),
                    positive=self._get_value("impact.amplifier.positive", 1.1),
                ),
                threshold=ImpactThresholdConfig(
                    viral=self._get_value("impact.threshold.viral", 70.0),
                    kol_followers=self._get_value(
                        "impact.threshold.kol_followers", 50000
                    ),
                    max_raw_score=self._get_value(
                        "impact.threshold.max_raw_score", 100000.0
                    ),
                ),
            ),
            batch=BatchConfig(
                max_concurrent=self._get_value("batch.max_concurrent", 5),
                timeout_seconds=self._get_value("batch.timeout_seconds", 30),
                expected_size=BatchExpectedSizeConfig(
                    tiktok=self._get_value("batch.expected_size.tiktok", 50),
                    youtube=self._get_value("batch.expected_size.youtube", 20),
                ),
            ),
            error=ErrorConfig(
                max_retries_per_item=self._get_value("error.max_retries_per_item", 3),
                backoff_base_seconds=self._get_value("error.backoff_base_seconds", 1.0),
                backoff_max_seconds=self._get_value("error.backoff_max_seconds", 60.0),
            ),
            debug=DebugConfig(
                raw_data=self._get_value("debug.raw_data", "false"),
                sample_rate=self._get_value("debug.sample_rate", 100),
            ),
            api=APIConfig(
                host=self._get_value("api.host", "0.0.0.0"),
                port=self._get_value("api.port", 8000),
                workers=self._get_value("api.workers", 1),
                cors_origins=(
                    self._get_value("api.cors_origins", ["*"])
                    if isinstance(self._get_value("api.cors_origins", ["*"]), list)
                    else ["*"]
                ),
                root_path=self._get_value("api.root_path", ""),
            ),
        )

    def _validate(self, config: Config) -> None:
        """Validate configuration."""
        errors = []

        # Validate database
        if not config.database.url:
            errors.append("database.url is required")

        # Validate RabbitMQ
        if not config.rabbitmq.url:
            errors.append("rabbitmq.url is required")

        # Validate MinIO
        if not config.minio.endpoint:
            errors.append("minio.endpoint is required")

        # Validate API port
        if config.api.port <= 0 or config.api.port > 65535:
            errors.append("api.port must be between 1 and 65535")

        if errors:
            raise ValueError(
                f"Configuration validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )


_config: Optional[Config] = None


def load_config() -> Config:
    """Load configuration (singleton).

    Returns:
        Config object
    """
    global _config
    if _config is None:
        loader = ConfigLoader()
        _config = loader.read_config()
    return _config


def get_config() -> Config:
    """Get loaded configuration.

    Returns:
        Config object
    """
    if _config is None:
        return load_config()
    return _config

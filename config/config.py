import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str = "postgresql+asyncpg://dev:dev123@localhost:5432/analytics_dev"
    url_sync: str = "postgresql://dev:dev123@localhost:5432/analytics_dev"
    pool_size: int = 20
    max_overflow: int = 10


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    debug: bool = False


@dataclass
class KafkaConfig:
    """Kafka configuration."""

    bootstrap_servers: str = "localhost:9092"
    topics: List[str] = field(default_factory=list)
    group_id: str = "analytics-service"


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
    min_size_bytes: int = 1024


@dataclass
class PreprocessorConfig:
    """Text preprocessor configuration."""

    min_text_length: int = 10
    max_comments: int = 5


@dataclass
class IntentClassifierConfig:
    """Intent classifier configuration."""

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
class Config:
    """Main configuration container.

    This is the root config object that contains all sub-configurations.
    Similar to Go's Viper config struct.
    """

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    minio: MinIOConfig = field(default_factory=MinIOConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    preprocessor: PreprocessorConfig = field(default_factory=PreprocessorConfig)
    intent_classifier: IntentClassifierConfig = field(
        default_factory=IntentClassifierConfig
    )
    impact: ImpactConfig = field(default_factory=ImpactConfig)


class ConfigLoader:
    """Viper-style configuration loader.

    Loads configuration from:
    1. YAML files (lowest priority)
    2. .env files
    3. Environment variables (highest priority)
    """

    def __init__(self):
        # Core loader settings actually used by the loader
        self.config_name = "config"
        self.config_paths = [".", "config", "/etc/analytics"]
        self.env_prefix = "ANALYTICS"
        self.auto_env = True
        self._raw_config: Dict[str, Any] = {}

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
            database=DatabaseConfig(
                url=self._get_value(
                    "database.url",
                    "postgresql+asyncpg://dev:dev123@localhost:5432/analytics_dev",
                ),
                url_sync=self._get_value(
                    "database.url_sync",
                    "postgresql://dev:dev123@localhost:5432/analytics_dev",
                ),
                pool_size=self._get_value("database.pool_size", 20),
                max_overflow=self._get_value("database.max_overflow", 10),
            ),
            logging=LoggingConfig(
                level=self._get_value("logging.level", "INFO"),
                debug=self._get_value("logging.debug", False),
            ),
            kafka=KafkaConfig(
                bootstrap_servers=self._get_value(
                    "kafka.bootstrap_servers", "localhost:9092"
                ),
                topics=self._get_value("kafka.topics", []),
                group_id=self._get_value("kafka.group_id", "analytics-service"),
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
                min_size_bytes=self._get_value("compression.min_size_bytes", 1024),
            ),
            preprocessor=PreprocessorConfig(
                min_text_length=self._get_value("preprocessor.min_text_length", 10),
                max_comments=self._get_value("preprocessor.max_comments", 5),
            ),
            intent_classifier=IntentClassifierConfig(
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
        )

    def _validate(self, config: Config) -> None:
        """Validate configuration."""
        errors = []

        # Validate database
        if not config.database.url:
            errors.append("database.url is required")

        # Validate Kafka
        if not config.kafka.bootstrap_servers:
            errors.append("kafka.bootstrap_servers is required")

        # Validate MinIO
        if not config.minio.endpoint:
            errors.append("minio.endpoint is required")

        if errors:
            raise ValueError(
                f"Configuration validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )


def load_config() -> Config:
    """Load configuration.

    Returns:
        Config object
    """
    return ConfigLoader().read_config()

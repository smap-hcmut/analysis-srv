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
    json_output: bool = False


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

    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
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
class ContractPublisherConfig:
    """Contract publisher configuration (knowledge-srv topics)."""

    batch_size: int = 100
    domain_overlay: str = ""
    enabled: bool = True


@dataclass
class KeywordExtractionConfig:
    """Keyword extraction configuration."""

    aspect_dictionary_path: str = "config/aspects_patterns.yaml"
    enable_ai: bool = True
    ai_threshold: int = 5
    max_keywords: int = 30


@dataclass
class SentimentAnalysisConfig:
    """Sentiment analysis configuration."""

    context_window_size: int = 100
    threshold_positive: float = 0.25
    threshold_negative: float = -0.25


@dataclass
class NLPConfig:
    """NLP batch enricher feature flags."""

    model_version: str = "1.0.0"
    enable_preprocessing: bool = True
    enable_intent_classification: bool = True
    enable_keyword_extraction: bool = True
    enable_sentiment_analysis: bool = True
    enable_impact_calculation: bool = True


@dataclass
class PipelineStagesConfig:
    """Pipeline stage feature flags."""

    enable_normalization: bool = True
    enable_dedup: bool = True
    enable_spam: bool = True
    enable_threads: bool = True
    enable_nlp: bool = True
    enable_enrichment: bool = True
    enable_review: bool = False
    enable_reporting: bool = False
    enable_crisis: bool = False


@dataclass
class OntologyConfig:
    """Ontology configuration — points to domain ontology YAML.

    Uses self-contained domain ontology files (OntologyRegistry format).
    The old 3-file split (entities/taxonomy/source_channels) is deprecated.
    """

    # Primary: self-contained domain ontology path
    domain_ontology_path: str = "config/ontology/vinfast_vn.yaml"

    # Legacy: kept for backwards compatibility, not used by new code
    entities_path: str = "config/ontology/entities.yaml"
    taxonomy_path: str = "config/ontology/taxonomy.yaml"
    source_channels_path: str = "config/ontology/source_channels.yaml"


@dataclass
class EnrichmentConfig:
    """Enrichment pipeline configuration."""

    entity_enabled: bool = True
    semantic_enabled: bool = True
    topic_enabled: bool = True
    source_influence_enabled: bool = True
    semantic_full_enabled: bool = True


@dataclass
class DomainRegistryConfig:
    """Domain registry configuration.

    Points to the directory containing per-domain YAML files
    (e.g. config/domains/vinfast.yaml, config/domains/_default.yaml).
    Each file is loaded at startup into the DomainRegistry for domain routing.
    """

    domains_dir: str = "config/domains"
    fallback_domain: str = "_default"


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
    contract_publisher: ContractPublisherConfig = field(
        default_factory=ContractPublisherConfig
    )
    keyword_extraction: KeywordExtractionConfig = field(
        default_factory=KeywordExtractionConfig
    )
    sentiment_analysis: SentimentAnalysisConfig = field(
        default_factory=SentimentAnalysisConfig
    )
    nlp: NLPConfig = field(default_factory=NLPConfig)
    pipeline: PipelineStagesConfig = field(default_factory=PipelineStagesConfig)
    ontology: OntologyConfig = field(default_factory=OntologyConfig)
    enrichment: EnrichmentConfig = field(default_factory=EnrichmentConfig)
    domain_registry: DomainRegistryConfig = field(default_factory=DomainRegistryConfig)


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
                json_output=self._get_value("logging.json_output", False),
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
                endpoint=self._get_value("minio.endpoint", ""),
                access_key=self._get_value("minio.access_key", ""),
                secret_key=self._get_value("minio.secret_key", ""),
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
            contract_publisher=ContractPublisherConfig(
                batch_size=self._get_value("contract_publisher.batch_size", 100),
                domain_overlay=self._get_value("contract_publisher.domain_overlay", ""),
                enabled=self._get_value("contract_publisher.enabled", True),
            ),
            keyword_extraction=KeywordExtractionConfig(
                aspect_dictionary_path=self._get_value(
                    "keyword_extraction.aspect_dictionary_path",
                    "config/aspects_patterns.yaml",
                ),
                enable_ai=self._get_value("keyword_extraction.enable_ai", True),
                ai_threshold=self._get_value("keyword_extraction.ai_threshold", 5),
                max_keywords=self._get_value("keyword_extraction.max_keywords", 30),
            ),
            sentiment_analysis=SentimentAnalysisConfig(
                context_window_size=self._get_value(
                    "sentiment_analysis.context_window_size", 100
                ),
                threshold_positive=self._get_value(
                    "sentiment_analysis.threshold_positive", 0.25
                ),
                threshold_negative=self._get_value(
                    "sentiment_analysis.threshold_negative", -0.25
                ),
            ),
            nlp=NLPConfig(
                model_version=self._get_value("nlp.model_version", "1.0.0"),
                enable_preprocessing=self._get_value("nlp.enable_preprocessing", True),
                enable_intent_classification=self._get_value(
                    "nlp.enable_intent_classification", True
                ),
                enable_keyword_extraction=self._get_value(
                    "nlp.enable_keyword_extraction", True
                ),
                enable_sentiment_analysis=self._get_value(
                    "nlp.enable_sentiment_analysis", True
                ),
                enable_impact_calculation=self._get_value(
                    "nlp.enable_impact_calculation", True
                ),
            ),
            pipeline=PipelineStagesConfig(
                enable_normalization=self._get_value(
                    "pipeline.enable_normalization", True
                ),
                enable_dedup=self._get_value("pipeline.enable_dedup", True),
                enable_spam=self._get_value("pipeline.enable_spam", True),
                enable_threads=self._get_value("pipeline.enable_threads", True),
                enable_nlp=self._get_value("pipeline.enable_nlp", True),
                enable_enrichment=self._get_value("pipeline.enable_enrichment", True),
                enable_review=self._get_value("pipeline.enable_review", False),
                enable_reporting=self._get_value("pipeline.enable_reporting", False),
                enable_crisis=self._get_value("pipeline.enable_crisis", False),
            ),
            ontology=OntologyConfig(
                domain_ontology_path=self._get_value(
                    "ontology.domain_ontology_path",
                    "config/ontology/vinfast_vn.yaml",
                ),
                entities_path=self._get_value(
                    "ontology.entities_path", "config/ontology/entities.yaml"
                ),
                taxonomy_path=self._get_value(
                    "ontology.taxonomy_path", "config/ontology/taxonomy.yaml"
                ),
                source_channels_path=self._get_value(
                    "ontology.source_channels_path",
                    "config/ontology/source_channels.yaml",
                ),
            ),
            enrichment=EnrichmentConfig(
                entity_enabled=self._get_value("enrichment.entity_enabled", True),
                semantic_enabled=self._get_value("enrichment.semantic_enabled", True),
                topic_enabled=self._get_value("enrichment.topic_enabled", True),
                source_influence_enabled=self._get_value(
                    "enrichment.source_influence_enabled", True
                ),
                semantic_full_enabled=self._get_value(
                    "enrichment.semantic_full_enabled", True
                ),
            ),
            domain_registry=DomainRegistryConfig(
                domains_dir=self._get_value(
                    "domain_registry.domains_dir", "config/domains"
                ),
                fallback_domain=self._get_value(
                    "domain_registry.fallback_domain", "_default"
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
        if not config.minio.access_key:
            errors.append("minio.access_key is required")
        if not config.minio.secret_key:
            errors.append("minio.secret_key is required")

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

from typing import Final, List

# Logger configuration
LOGGER_SERVICE_NAME: Final[str] = "analytics-engine"
LOGGER_ENABLE_CONSOLE: Final[bool] = True
LOGGER_COLORIZE: Final[bool] = True
LOGGER_ENABLE_TRACE_ID: Final[bool] = False

# PostgreSQL configuration
POSTGRES_SCHEMA: Final[str] = "analytics"

# PhoBERT sentiment model
PHOBERT_MODEL_PATH: Final[str] = "internal/model/phobert"
PHOBERT_MAX_LENGTH: Final[int] = 256

# SpaCy-YAKE keyword extraction
SPACY_MODEL: Final[str] = "xx_ent_wiki_sm"
SPACY_YAKE_LANGUAGE: Final[str] = "vi"
SPACY_YAKE_N: Final[int] = 2
SPACY_YAKE_DEDUP_LIM: Final[float] = 0.8
SPACY_YAKE_MAX_KEYWORDS: Final[int] = 30
SPACY_MAX_KEYWORDS: Final[int] = 30
SPACY_ENTITY_WEIGHT: Final[float] = 0.7
SPACY_CHUNK_WEIGHT: Final[float] = 0.5

# Kafka integration (consumer & producer)
KAFKA_DEFAULT_TOPICS: Final[List[str]] = ["smap.collector.output"]
KAFKA_DEFAULT_GROUP_ID: Final[str] = "analytics-service"
KAFKA_PRODUCER_ACKS: Final[str] = "all"
KAFKA_PRODUCER_COMPRESSION_TYPE: Final[str] = "gzip"
KAFKA_PRODUCER_ENABLE_IDEMPOTENCE: Final[bool] = True
KAFKA_PRODUCER_LINGER_MS: Final[int] = 100

from dataclasses import dataclass

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.postgre.postgres import PostgresDatabase
from pkg.redis.redis import RedisCache
from pkg.minio.minio import MinioAdapter
from pkg.zstd.zstd import Zstd
from config.config import Config


@dataclass
class Dependencies:
    """Dependencies container for consumer service.

    This struct holds all initialized service dependencies that will be
    injected into the consumer server.

    Attributes:
        logger: Logger instance for structured logging
        db: PostgreSQL database instance
        redis: Redis cache instance
        minio: MinIO storage instance
        zstd: Zstd compressor instance
        sentiment: PhoBERT sentiment analyzer
        keyword_extractor: SpaCy-YAKE keyword extractor
        config: Application configuration
    """

    logger: Logger
    db: PostgresDatabase
    redis: RedisCache
    minio: MinioAdapter
    zstd: Zstd
    sentiment: PhoBERTONNX
    keyword_extractor: SpacyYake
    config: Config


__all__ = ["Dependencies"]

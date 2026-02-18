from dataclasses import dataclass
from typing import Optional

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.postgre.postgres import PostgresDatabase
from pkg.redis.redis import RedisCache
from pkg.minio.minio import MinioAdapter
from pkg.zstd.zstd import Zstd
from pkg.kafka.producer import KafkaProducer
from pkg.kafka.type import KafkaConsumerConfig
from config.config import Config


@dataclass
class Dependencies:
    logger: Logger
    db: PostgresDatabase
    redis: RedisCache
    minio: MinioAdapter
    zstd: Zstd
    sentiment: PhoBERTONNX
    keyword_extractor: SpacyYake
    config: Config
    kafka_producer: Optional[KafkaProducer] = None
    kafka_consumer_config: KafkaConsumerConfig | None = None


__all__ = ["Dependencies"]

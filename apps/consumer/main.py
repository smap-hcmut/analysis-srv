import asyncio
import signal

from pkg.logger.logger import Logger, LoggerConfig
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.phobert_onnx.type import PhoBERTConfig
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.spacy_yake.type import SpacyYakeConfig
from pkg.postgre.postgres import PostgresDatabase
from pkg.postgre.type import PostgresConfig
from pkg.redis.redis import RedisCache
from pkg.redis.type import RedisConfig as RedisPkgConfig
from pkg.minio.minio import MinioAdapter
from pkg.minio.type import MinIOConfig as MinioPkgConfig, CompressionConfig
from pkg.zstd.zstd import Zstd
from pkg.zstd.type import ZstdConfig
from pkg.kafka.producer import KafkaProducer
from pkg.kafka.type import (
    KafkaProducerConfig as KafkaProducerPkgConfig,
    KafkaConsumerConfig as KafkaConsumerPkgConfig,
)
from config.config import load_config, Config
from internal.consumer import KafkaConsumerServer, Dependencies
from internal.model.constant import (
    LOGGER_SERVICE_NAME,
    LOGGER_ENABLE_CONSOLE,
    LOGGER_COLORIZE,
    LOGGER_ENABLE_TRACE_ID,
    POSTGRES_SCHEMA,
    PHOBERT_MODEL_PATH,
    PHOBERT_MAX_LENGTH,
    SPACY_MODEL,
    SPACY_YAKE_LANGUAGE,
    SPACY_YAKE_N,
    SPACY_YAKE_DEDUP_LIM,
    SPACY_YAKE_MAX_KEYWORDS,
    SPACY_MAX_KEYWORDS,
    SPACY_ENTITY_WEIGHT,
    SPACY_CHUNK_WEIGHT,
    KAFKA_DEFAULT_TOPICS,
    KAFKA_PRODUCER_ACKS,
    KAFKA_PRODUCER_COMPRESSION_TYPE,
    KAFKA_PRODUCER_ENABLE_IDEMPOTENCE,
    KAFKA_PRODUCER_LINGER_MS,
)


async def init_dependencies(config: Config) -> Dependencies:
    """Initialize all service dependencies.

    Args:
        config: Application configuration

    Returns:
        Dependencies struct with all initialized instances
    """
    # Initialize logger
    logger = Logger(
        LoggerConfig(
            level=config.logging.level,
            enable_console=LOGGER_ENABLE_CONSOLE,
            colorize=LOGGER_COLORIZE,
            service_name=LOGGER_SERVICE_NAME,
            enable_trace_id=LOGGER_ENABLE_TRACE_ID,
        )
    )
    logger.info("Logger initialized")

    # Initialize PostgreSQL database
    db = PostgresDatabase(
        PostgresConfig(
            database_url=config.database.url,
            schema=POSTGRES_SCHEMA,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
        )
    )
    if not await db.health_check():
        raise RuntimeError("PostgreSQL health check failed")
    logger.info("PostgreSQL connection verified")

    # Initialize Redis
    redis = RedisCache(
        RedisPkgConfig(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            max_connections=config.redis.max_connections,
        )
    )
    if not await redis.health_check():
        raise RuntimeError("Redis health check failed")
    logger.info("Redis connection verified")

    # Initialize MinIO
    minio = MinioAdapter(
        MinioPkgConfig(
            endpoint=config.minio.endpoint,
            access_key=config.minio.access_key,
            secret_key=config.minio.secret_key,
            secure=config.minio.secure,
        ),
        CompressionConfig(
            enabled=config.compression.enabled,
            algorithm="zstd",
            level=config.compression.default_level,
            min_size_bytes=config.compression.min_size_bytes,
        ),
    )
    logger.info("MinIO storage initialized")

    # Initialize Data compressor
    data_compressor = Zstd(
        ZstdConfig(
            default_level=config.compression.default_level,
        )
    )
    logger.info("Data compressor initialized")

    # Initialize Sentiment analyzer
    sentiment = PhoBERTONNX(
        PhoBERTConfig(
            model_path=PHOBERT_MODEL_PATH,
            max_length=PHOBERT_MAX_LENGTH,
        )
    )
    logger.info("Sentiment analyzer initialized")

    # Initialize Keyword extractor
    keyword_extractor = SpacyYake(
        SpacyYakeConfig(
            spacy_model=SPACY_MODEL,
            yake_language=SPACY_YAKE_LANGUAGE,
            yake_n=SPACY_YAKE_N,
            yake_dedup_lim=SPACY_YAKE_DEDUP_LIM,
            yake_max_keywords=SPACY_YAKE_MAX_KEYWORDS,
            max_keywords=SPACY_MAX_KEYWORDS,
            entity_weight=SPACY_ENTITY_WEIGHT,
            chunk_weight=SPACY_CHUNK_WEIGHT,
        )
    )
    logger.info("Keyword extractor initialized")

    # Initialize Kafka Producer
    kafka_producer = KafkaProducer(
        KafkaProducerPkgConfig(
            bootstrap_servers=config.kafka.bootstrap_servers,
            acks=KAFKA_PRODUCER_ACKS,
            compression_type=KAFKA_PRODUCER_COMPRESSION_TYPE,
            enable_idempotence=KAFKA_PRODUCER_ENABLE_IDEMPOTENCE,
            linger_ms=KAFKA_PRODUCER_LINGER_MS,
        )
    )
    await kafka_producer.start()
    logger.info("Kafka producer initialized")

    # Build Kafka consumer config (used by internal KafkaConsumerServer)
    topics = config.kafka.topics or KAFKA_DEFAULT_TOPICS
    kafka_consumer_config = KafkaConsumerPkgConfig(
        bootstrap_servers=config.kafka.bootstrap_servers,
        topics=topics,
        group_id=config.kafka.group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=10,
        session_timeout_ms=30000,
    )

    return Dependencies(
        logger=logger,
        db=db,
        redis=redis,
        minio=minio,
        zstd=data_compressor,
        sentiment=sentiment,
        keyword_extractor=keyword_extractor,
        config=config,
        kafka_producer=kafka_producer,
        kafka_consumer_config=kafka_consumer_config,
    )


async def main():
    """Main entry point for analytics consumer service.

    Raises:
        Exception: If service fails to start
    """
    # Initialize deps - safe cleanup
    deps = None
    server = None
    logger = None

    try:
        # Load configuration
        app_config = load_config()

        # Initialize all dependencies
        deps = await init_dependencies(app_config)
        logger = deps.logger

        # Create Kafka consumer server
        server = KafkaConsumerServer(deps)

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()

        def signal_handler(sig):
            """Handle shutdown signals."""
            logger.info(f"Received signal {sig}, shutting down gracefully...")
            # Create task to shutdown server
            if server:
                asyncio.create_task(server.shutdown())

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        # Start server
        await server.start()

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Failed to start consumer: {e}")
        logger.exception("Consumer startup error:")
    finally:
        if server:
            await server.shutdown()
        # Cleanup Kafka producer
        logger.info("Cleaning up dependencies...")
        try:
            if deps and deps.kafka_producer:
                await deps.kafka_producer.stop()
        except Exception as e:
            logger.error(f"Error stopping Kafka producer: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise


def run():
    """Entry point for console script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")

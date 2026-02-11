import asyncio
import signal

from pkg.logger.logger import Logger, LoggerConfig
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.phobert_onnx.type import PhoBERTConfig
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.spacy_yake.type import SpacyYakeConfig
from pkg.rabbitmq.consumer import RabbitMQClient
from pkg.rabbitmq.type import RabbitMQConfig
from pkg.postgre.postgres import PostgresDatabase
from pkg.postgre.type import PostgresConfig
from pkg.redis.redis import RedisCache
from pkg.redis.type import RedisConfig as RedisPkgConfig
from pkg.minio.minio import MinioAdapter
from pkg.minio.type import MinIOConfig as MinioPkgConfig, CompressionConfig
from pkg.zstd.zstd import Zstd
from pkg.zstd.type import ZstdConfig
from config.config import load_config, Config
from internal.consumer import ConsumerServer, Dependencies


def init_dependencies(config: Config) -> Dependencies:
    """Initialize all service dependencies.

    Args:
        config: Application configuration

    Returns:
        Dependencies struct with all initialized instances
    """
    # 1. Initialize logger
    logger = Logger(
        LoggerConfig(
            level=config.logging.level,
            enable_console=config.logging.enable_console,
            colorize=config.logging.colorize,
            service_name=config.logging.service_name,
            enable_trace_id=False,
        )
    )
    logger.info("Logger initialized")

    # 2. Initialize PostgreSQL database
    db = PostgresDatabase(
        PostgresConfig(
            database_url=config.database.url,
            schema=config.database.schema,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
        )
    )
    logger.info("PostgreSQL initialized")

    # 3. Initialize Redis cache
    redis = RedisCache(
        RedisPkgConfig(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            max_connections=config.redis.max_connections,
        )
    )
    logger.info("Redis cache initialized")

    # 4. Initialize MinIO storage
    minio = MinioAdapter(
        MinioPkgConfig(
            endpoint=config.minio.endpoint,
            access_key=config.minio.access_key,
            secret_key=config.minio.secret_key,
            secure=config.minio.secure,
        ),
        CompressionConfig(
            enabled=config.compression.enabled,
            algorithm=config.compression.algorithm,
            level=config.compression.default_level,
            min_size_bytes=config.compression.min_size_bytes,
        ),
    )
    logger.info("MinIO storage initialized")

    # 5. Initialize Zstd compressor
    zstd_compressor = Zstd(
        ZstdConfig(
            default_level=config.compression.default_level,
        )
    )
    logger.info("Zstd compressor initialized")

    # 6. Initialize sentiment analyzer (PhoBERT)
    sentiment = PhoBERTONNX(
        PhoBERTConfig(
            model_path=config.phobert.model_path,
            max_length=config.phobert.max_length,
        )
    )
    logger.info("Sentiment analyzer initialized")

    # 7. Initialize keyword extractor (SpaCy-YAKE)
    keyword_extractor = SpacyYake(
        SpacyYakeConfig(
            spacy_model=config.keyword_extraction.spacy_model,
            yake_language=config.keyword_extraction.yake_language,
            yake_n=config.keyword_extraction.yake_n,
            yake_dedup_lim=config.keyword_extraction.yake_dedup_lim,
            yake_max_keywords=config.keyword_extraction.yake_max_keywords,
            max_keywords=config.keyword_extraction.max_keywords,
            entity_weight=config.keyword_extraction.entity_weight,
            chunk_weight=config.keyword_extraction.chunk_weight,
        )
    )
    logger.info("Keyword extractor initialized")

    # 8. Initialize RabbitMQ client
    rabbitmq = RabbitMQClient(
        RabbitMQConfig(
            url=config.rabbitmq.url,
            queue_name=config.rabbitmq.event.queue_name,
            prefetch_count=config.rabbitmq.prefetch_count,
            exchange_name=config.rabbitmq.event.exchange,
            routing_key=config.rabbitmq.event.routing_key,
        )
    )
    logger.info("RabbitMQ client initialized")

    # 9. Return dependencies struct
    return Dependencies(
        logger=logger,
        db=db,
        redis=redis,
        minio=minio,
        zstd=zstd_compressor,
        sentiment=sentiment,
        keyword_extractor=keyword_extractor,
        rabbitmq=rabbitmq,
        config=config,
    )


async def main():
    """Main entry point for analytics consumer service.

    Flow:
    1. Load configuration
    2. Initialize dependencies (logger, sentiment, keyword_extractor, rabbitmq)
    3. Create consumer server with dependencies
    4. Start server (register handlers and begin consuming)
    """
    server = None

    try:
        # 1. Load configuration
        app_config = load_config()
        print(
            f"Configuration loaded: {app_config.service.name} v{app_config.service.version}"
        )

        # 2. Initialize all dependencies
        deps = init_dependencies(app_config)

        # 3. Create consumer server with dependencies
        server = ConsumerServer(deps)

        # 4. Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()

        def signal_handler(sig):
            """Handle shutdown signals."""
            print(f"\nReceived signal {sig}, shutting down gracefully...")
            # Create task to shutdown server
            asyncio.create_task(server.shutdown())

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        # 5. Start server (this will register handlers and start consuming)
        await server.start()

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error starting consumer: {e}")
        raise
    finally:
        if server:
            await server.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")


# Entry point for script
def run():
    """Entry point for console script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")

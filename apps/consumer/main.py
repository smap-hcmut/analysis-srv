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
from config.config import load_config, Config
from internal.consumer import ConsumerServer, Dependencies


async def init_dependencies(config: Config) -> Dependencies:
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
    if not await db.health_check():
        raise RuntimeError("PostgreSQL health check failed")
    logger.info("PostgreSQL connection verified")

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
    if not await redis.health_check():
        raise RuntimeError("Redis health check failed")
    logger.info("Redis connection verified")

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

    return Dependencies(
        logger=logger,
        db=db,
        redis=redis,
        minio=minio,
        zstd=zstd_compressor,
        sentiment=sentiment,
        keyword_extractor=keyword_extractor,
        config=config,
    )


async def main():
    """Main entry point for analytics consumer service.

    Flow:
    1. Load configuration
    2. Initialize dependencies (logger, db, redis, etc.)
    3. Create consumer server (registry initialized inside server.start())
    4. Start server
    """
    server = None
    logger = None

    try:
        # 1. Load configuration
        app_config = load_config()
        print(
            f"Configuration loaded: {app_config.service.name} v{app_config.service.version}"
        )

        # 2. Initialize all dependencies
        deps = await init_dependencies(app_config)
        logger = deps.logger

        # 3. Create consumer server
        server = ConsumerServer(deps)

        # 4. Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()

        def signal_handler(sig):
            """Handle shutdown signals."""
            logger.info(f"Received signal {sig}, shutting down gracefully...")
            # Create task to shutdown server
            asyncio.create_task(server.shutdown())

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        # 5. Start server
        await server.start()

    except KeyboardInterrupt:
        if logger:
            logger.info("Shutdown requested by user")
        else:
            print("\nShutdown requested by user")
    except Exception as e:
        if logger:
            logger.error(f"Failed to start consumer: {e}")
            logger.exception("Consumer startup error:")
        else:
            print(f"Error starting consumer: {e}")
            import traceback

            traceback.print_exc()
        # Exit with error code
        import sys

        sys.exit(1)
    finally:
        if server:
            await server.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled in main()
    except SystemExit:
        raise  # Preserve exit code


# Entry point for script
def run():
    """Entry point for console script."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")

import asyncio
import signal

from pkg.logger.logger import Logger, LoggerConfig
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from pkg.phobert_onnx.type import PhoBERTConfig
from pkg.spacy_yake.spacy_yake import SpacyYake
from pkg.spacy_yake.type import SpacyYakeConfig
from pkg.rabbitmq.consumer import RabbitMQClient
from pkg.rabbitmq.type import RabbitMQConfig
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
        )
    )
    logger.info("Logger initialized")

    # 2. Initialize sentiment analyzer (PhoBERT)
    sentiment = PhoBERTONNX(
        PhoBERTConfig(
            model_path=config.phobert.model_path,
            max_length=config.phobert.max_length,
        )
    )
    logger.info("Sentiment analyzer initialized")

    # 3. Initialize keyword extractor (SpaCy-YAKE)
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

    # 4. Initialize RabbitMQ client
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

    # 5. Return dependencies struct
    return Dependencies(
        logger=logger,
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
        deps.logger.info("All dependencies initialized")

        # 3. Create consumer server with dependencies
        deps.logger.info("Creating consumer server...")
        server = ConsumerServer(deps)
        deps.logger.info("Consumer server created")

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
        deps.logger.info("Starting consumer server...")
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

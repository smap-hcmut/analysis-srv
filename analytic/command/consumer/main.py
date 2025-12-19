"""
Analytics Engine Consumer - Main entry point.
Loads config, initializes AI models and RabbitMQ, starts the consumer service.
Publishes analyze results to Collector service.
"""

import asyncio
from typing import Optional

from core.config import settings
from core.logger import logger
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from infrastructure.messaging import RabbitMQClient, RabbitMQPublisher
from internal.consumers.main import create_message_handler


# Global instances - reused for all messages
phobert: Optional[PhoBERTONNX] = None
spacyyake: Optional[SpacyYakeExtractor] = None
rabbitmq_client: Optional[RabbitMQClient] = None
rabbitmq_publisher: Optional[RabbitMQPublisher] = None


async def main():
    """Entry point for the Analytics Engine consumer."""
    global phobert, spacyyake, rabbitmq_client, rabbitmq_publisher

    try:
        logger.info(
            f"========== Starting {settings.service_name} v{settings.service_version} Consumer service =========="
        )

        # 1. Initialize AI models
        logger.info("Loading AI models...")

        # Track model initialization status for health check
        phobert_status = {"enabled": False, "error": None}
        spacyyake_status = {"enabled": False, "error": None}

        try:
            # Initialize PhoBERT
            logger.info("Initializing PhoBERT ONNX model...")
            logger.info(f"PhoBERT model path: {settings.phobert_model_path}")
            phobert = PhoBERTONNX(
                model_path=settings.phobert_model_path, max_length=settings.phobert_max_length
            )
            phobert_status["enabled"] = True
            logger.info("PhoBERT ONNX model loaded successfully. " "Sentiment analysis is ENABLED.")

        except FileNotFoundError as e:
            phobert_status["error"] = str(e)
            logger.error(
                f"PhoBERT model files not found: {e}. "
                "Sentiment analysis will be DISABLED. "
                f"Please ensure model files exist at: {settings.phobert_model_path}"
            )
            phobert = None

        except Exception as e:
            phobert_status["error"] = str(e)
            logger.error(
                f"Failed to initialize PhoBERT model: {e}. Sentiment analysis will be DISABLED."
            )
            logger.exception("PhoBERT initialization error details:")
            phobert = None

        try:
            # Initialize SpaCy-YAKE
            logger.info("Initializing SpaCy-YAKE extractor...")
            spacyyake = SpacyYakeExtractor(
                spacy_model=settings.spacy_model,
                yake_language=settings.yake_language,
                yake_n=settings.yake_n,
                yake_dedup_lim=settings.yake_dedup_lim,
                yake_max_keywords=settings.yake_max_keywords,
                max_keywords=settings.max_keywords,
                entity_weight=settings.entity_weight,
                chunk_weight=settings.chunk_weight,
            )
            spacyyake_status["enabled"] = True
            logger.info("SpaCy-YAKE extractor loaded successfully")

        except Exception as e:
            spacyyake_status["error"] = str(e)
            logger.error(f"Failed to initialize SpaCy-YAKE: {e}")
            logger.exception("SpaCy-YAKE initialization error details:")
            spacyyake = None

        # Log AI model health summary
        logger.info("=" * 50)
        logger.info("AI Model Health Check Summary:")
        phobert_msg = (
            "ENABLED" if phobert_status["enabled"] else f"DISABLED ({phobert_status['error']})"
        )
        spacyyake_msg = (
            "ENABLED" if spacyyake_status["enabled"] else f"DISABLED ({spacyyake_status['error']})"
        )
        logger.info(f"  - PhoBERT (Sentiment): {phobert_msg}")
        logger.info(f"  - SpaCy-YAKE (Keywords): {spacyyake_msg}")
        logger.info("=" * 50)

        if not phobert_status["enabled"]:
            logger.warning(
                "WARNING: Sentiment analysis is disabled! "
                "All posts will receive neutral sentiment scores (NEUTRAL, score=0.0). "
                "This significantly reduces analytics value."
            )

        # 2. Initialize RabbitMQ client
        logger.info("Initializing RabbitMQ client...")

        # Event-driven mode configuration
        queue_name = settings.event_queue_name
        exchange_name = settings.event_exchange
        routing_key = settings.event_routing_key
        logger.info(
            f"Connecting to event queue: exchange={exchange_name}, routing_key={routing_key}, queue={queue_name}"
        )

        rabbitmq_client = RabbitMQClient(
            rabbitmq_url=settings.rabbitmq_url,
            queue_name=queue_name,
            prefetch_count=settings.rabbitmq_prefetch_count,
        )

        # Connect to RabbitMQ with optional exchange binding
        await rabbitmq_client.connect(
            exchange_name=exchange_name,
            routing_key=routing_key,
        )

        # 3. Initialize RabbitMQ publisher for result publishing
        if settings.publish_enabled:
            logger.info("Initializing RabbitMQ publisher...")
            logger.info(
                f"Publisher config: exchange={settings.publish_exchange}, routing_key={settings.publish_routing_key}"
            )

            # Create publisher using the same channel as consumer
            rabbitmq_publisher = RabbitMQPublisher(
                channel=rabbitmq_client.channel,
                exchange_name=settings.publish_exchange,
                routing_key=settings.publish_routing_key,
            )

            # Setup publisher (declare exchange)
            await rabbitmq_publisher.setup()
            logger.info("RabbitMQ publisher initialized successfully")
        else:
            logger.info("Result publishing is disabled (publish_enabled=False)")
            rabbitmq_publisher = None

        # 4. Create message handler with AI model instances and publisher
        message_handler = create_message_handler(
            phobert=phobert,
            spacyyake=spacyyake,
            publisher=rabbitmq_publisher,
        )

        # 5. Start consuming messages
        logger.info(f"Starting message consumption from queue '{settings.rabbitmq_queue_name}'...")
        await rabbitmq_client.consume(message_handler)

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Consumer error: {e}")
        logger.exception("Consumer error details:")
        raise
    finally:
        # Cleanup sequence
        logger.info("========== Shutting down Consumer service ==========")

        # Close RabbitMQ connection (publisher uses same connection)
        if rabbitmq_client:
            await rabbitmq_client.close()
            logger.info("RabbitMQ connection closed")

        # Cleanup AI models
        if phobert:
            del phobert
            logger.info("PhoBERT model cleaned up")
        if spacyyake:
            del spacyyake
            logger.info("SpaCy-YAKE extractor cleaned up")

        logger.info("========== Consumer service stopped ==========")


if __name__ == "__main__":
    asyncio.run(main())

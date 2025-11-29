"""
Analytics Engine Consumer - Main entry point.
Loads config, initializes AI models and RabbitMQ, starts the consumer service.
"""

import asyncio
from typing import Optional

from core.config import settings
from core.logger import logger
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from infrastructure.messaging import RabbitMQClient
from internal.consumers.main import create_message_handler


# Global instances (initialized once, reused for all messages)
phobert: Optional[PhoBERTONNX] = None
spacyyake: Optional[SpacyYakeExtractor] = None
rabbitmq_client: Optional[RabbitMQClient] = None


async def main():
    """Entry point for the Analytics Engine consumer."""
    global phobert, spacyyake, rabbitmq_client

    try:
        logger.info(
            f"========== Starting {settings.service_name} v{settings.service_version} Consumer service =========="
        )

        # 1. Initialize AI models
        logger.info("Loading AI models...")

        try:
            # Initialize PhoBERT
            logger.info("Initializing PhoBERT ONNX model...")
            phobert = PhoBERTONNX(
                model_path=settings.phobert_model_path, max_length=settings.phobert_max_length
            )
            logger.info("PhoBERT ONNX model loaded successfully")

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
            logger.info("SpaCy-YAKE extractor loaded successfully")

            logger.info("All AI models loaded successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
            logger.exception("Model initialization error details:")
            logger.warning("Consumer will start without AI models")

        # 2. Initialize RabbitMQ client
        logger.info("Initializing RabbitMQ client...")
        rabbitmq_client = RabbitMQClient(
            rabbitmq_url=settings.rabbitmq_url,
            queue_name=settings.rabbitmq_queue_name,
            prefetch_count=settings.rabbitmq_prefetch_count,
        )

        # Connect to RabbitMQ
        await rabbitmq_client.connect()

        # 3. Create message handler with AI model instances
        message_handler = create_message_handler(phobert=phobert, spacyyake=spacyyake)

        # 4. Start consuming messages
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

        # Close RabbitMQ connection
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

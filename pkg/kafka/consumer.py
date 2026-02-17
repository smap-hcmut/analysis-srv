from typing import Callable, Optional, Awaitable
from aiokafka import AIOKafkaConsumer  # type: ignore
from loguru import logger
from .interface import IKafkaConsumer
from .type import KafkaConsumerConfig, KafkaMessage, KafkaConsumerError


class KafkaConsumer(IKafkaConsumer):
    """Kafka consumer for robust message consumption.

    This class manages the lifecycle of Kafka consumer connections and provides
    methods for consuming messages with proper offset management.

    Attributes:
        config: Kafka consumer configuration
        consumer: Active Kafka consumer instance
    """

    def __init__(self, config: KafkaConsumerConfig):
        """Initialize Kafka consumer with configuration.

        Args:
            config: Kafka consumer configuration
        """
        self.config = config
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._running = False

        logger.info(
            f"Kafka consumer initialized (topics={config.topics}, group_id={config.group_id})"
        )

    async def start(self) -> None:
        """Start the consumer and connect to Kafka.

        Creates a consumer instance and subscribes to configured topics.

        Raises:
            KafkaConsumerError: If connection fails
        """
        try:
            logger.info(
                f"Starting Kafka consumer (bootstrap_servers={self.config.bootstrap_servers})..."
            )

            # Create consumer
            self.consumer = AIOKafkaConsumer(
                *self.config.topics,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=self.config.group_id,
                auto_offset_reset=self.config.auto_offset_reset,
                enable_auto_commit=self.config.enable_auto_commit,
                max_poll_records=self.config.max_poll_records,
                session_timeout_ms=self.config.session_timeout_ms,
                client_id=self.config.client_id,
            )

            # Start consumer
            await self.consumer.start()
            self._running = True

            logger.info(
                f"Kafka consumer started successfully (topics={self.config.topics}, "
                f"group_id={self.config.group_id})"
            )

        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            logger.exception("Kafka consumer start error details:")
            raise KafkaConsumerError(f"Failed to start consumer: {e}") from e

    async def stop(self) -> None:
        """Stop the consumer gracefully.

        Closes the consumer connection and cleans up resources.
        """
        try:
            logger.info("Stopping Kafka consumer...")

            if self.consumer:
                await self.consumer.stop()
                self._running = False
                logger.info("Kafka consumer stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping Kafka consumer: {e}")
            logger.exception("Kafka consumer stop error details:")

    async def consume(
        self, message_handler: Callable[[KafkaMessage], Awaitable[None]]
    ) -> None:
        """Start consuming messages from subscribed topics.

        This method runs indefinitely, processing messages as they arrive.

        Args:
            message_handler: Async callable to process incoming messages.
                             Should accept KafkaMessage.

        Raises:
            RuntimeError: If consumer is not started
            KafkaConsumerError: If consumption fails
        """
        if not self.consumer or not self._running:
            raise RuntimeError("Consumer not started. Call start() first.")

        try:
            logger.info(
                f"Starting message consumption from topics {self.config.topics}..."
            )

            async for msg in self.consumer:
                try:
                    # Convert aiokafka message to our KafkaMessage model
                    kafka_msg = KafkaMessage(
                        topic=msg.topic,
                        partition=msg.partition,
                        offset=msg.offset,
                        value=msg.value,
                        key=msg.key,
                        timestamp=msg.timestamp,
                        headers=dict(msg.headers) if msg.headers else {},
                    )

                    # Process message
                    await message_handler(kafka_msg)

                    logger.debug(
                        f"Processed message: topic={msg.topic}, partition={msg.partition}, "
                        f"offset={msg.offset}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing message from topic={msg.topic}, "
                        f"partition={msg.partition}, offset={msg.offset}: {e}"
                    )
                    logger.exception("Message processing error details:")
                    # Continue processing other messages

        except Exception as e:
            logger.error(f"Error during message consumption: {e}")
            logger.exception("Consumption error details:")
            raise KafkaConsumerError(f"Consumption failed: {e}") from e

    async def commit(self) -> None:
        """Manually commit offsets.

        Only needed if enable_auto_commit is False.

        Raises:
            RuntimeError: If consumer is not started
        """
        if not self.consumer or not self._running:
            raise RuntimeError("Consumer not started. Call start() first.")

        try:
            await self.consumer.commit()
            logger.debug("Offsets committed successfully")
        except Exception as e:
            logger.error(f"Failed to commit offsets: {e}")
            raise KafkaConsumerError(f"Commit failed: {e}") from e

    def is_running(self) -> bool:
        """Check if consumer is running.

        Returns:
            bool: True if running, False otherwise
        """
        return self._running and self.consumer is not None


__all__ = [
    "IKafkaConsumer",
    "KafkaConsumer",
]

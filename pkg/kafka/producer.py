import json
from typing import Optional, Dict, List, Protocol, runtime_checkable
from aiokafka import AIOKafkaProducer  # type: ignore
from loguru import logger
from .type import KafkaProducerConfig


@runtime_checkable
class IKafkaProducer(Protocol):
    """Protocol defining the Kafka producer interface."""

    async def start(self) -> None:
        """Start the producer and connect to Kafka."""
        ...

    async def stop(self) -> None:
        """Stop the producer gracefully."""
        ...

    async def send(
        self,
        topic: str,
        value: bytes,
        key: Optional[bytes] = None,
        partition: Optional[int] = None,
        headers: Optional[Dict[str, bytes]] = None,
    ) -> None:
        """Send a message to Kafka topic."""
        ...

    async def send_batch(self, messages: List[Dict[str, bytes]]) -> None:
        """Send multiple messages in batch."""
        ...

    def is_running(self) -> bool:
        """Check if producer is running."""
        ...


class KafkaProducerError(Exception):
    """Base exception for Kafka producer operations."""

    pass


class KafkaProducer(IKafkaProducer):
    """Kafka producer for sending messages to topics.

    This class manages the lifecycle of Kafka producer connections and provides
    methods for sending messages with proper serialization.

    Attributes:
        config: Kafka producer configuration
        producer: Active Kafka producer instance
    """

    def __init__(self, config: KafkaProducerConfig):
        """Initialize Kafka producer with configuration.

        Args:
            config: Kafka producer configuration
        """
        self.config = config
        self.producer: Optional[AIOKafkaProducer] = None
        self._running = False

        logger.info(
            f"Kafka producer initialized (bootstrap_servers={config.bootstrap_servers}, "
            f"acks={config.acks})"
        )

    async def start(self) -> None:
        """Start the producer and connect to Kafka.

        Creates a producer instance and establishes connection.

        Raises:
            KafkaProducerError: If connection fails
        """
        try:
            logger.info(
                f"Starting Kafka producer (bootstrap_servers={self.config.bootstrap_servers})..."
            )

            # Create producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                acks=self.config.acks,
                compression_type=self.config.compression_type,
                max_batch_size=self.config.max_batch_size,
                linger_ms=self.config.linger_ms,
                client_id=self.config.client_id,
                enable_idempotence=self.config.enable_idempotence,
            )

            # Start producer
            await self.producer.start()
            self._running = True

            logger.info(
                f"Kafka producer started successfully (acks={self.config.acks}, "
                f"compression={self.config.compression_type})"
            )

        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            logger.exception("Kafka producer start error details:")
            raise KafkaProducerError(f"Failed to start producer: {e}") from e

    async def stop(self) -> None:
        """Stop the producer gracefully.

        Flushes pending messages and closes the producer connection.
        """
        try:
            logger.info("Stopping Kafka producer...")

            if self.producer:
                # Flush pending messages
                await self.producer.flush()
                await self.producer.stop()
                self._running = False
                logger.info("Kafka producer stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping Kafka producer: {e}")
            logger.exception("Kafka producer stop error details:")

    async def send(
        self,
        topic: str,
        value: bytes,
        key: Optional[bytes] = None,
        partition: Optional[int] = None,
        headers: Optional[Dict[str, bytes]] = None,
    ) -> None:
        """Send a message to Kafka topic.

        Args:
            topic: Topic name
            value: Message value (bytes)
            key: Optional message key (bytes)
            partition: Optional partition number
            headers: Optional message headers

        Raises:
            RuntimeError: If producer is not started
            KafkaProducerError: If sending fails

        Example:
            ```python
            await producer.send(
                topic="analytics_topic",
                value=json.dumps({"status": "ok"}).encode(),
                key=b"key123"
            )
            ```
        """
        if not self.producer or not self._running:
            raise RuntimeError("Producer not started. Call start() first.")

        try:
            # Convert headers to list of tuples if provided
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v) for k, v in headers.items()]

            # Send message
            await self.producer.send(
                topic=topic,
                value=value,
                key=key,
                partition=partition,
                headers=kafka_headers,
            )

            logger.debug(
                f"Sent message to topic={topic}, partition={partition}, "
                f"key={key[:20] if key else None}, size={len(value)} bytes"
            )

        except Exception as e:
            logger.error(f"Failed to send message to topic={topic}: {e}")
            raise KafkaProducerError(f"Send failed: {e}") from e

    async def send_json(
        self,
        topic: str,
        value: Dict[str, object],
        key: Optional[str] = None,
        partition: Optional[int] = None,
        headers: Optional[Dict[str, bytes]] = None,
    ) -> None:
        """Send a JSON message to Kafka topic.

        Convenience method that serializes dict to JSON bytes.

        Args:
            topic: Topic name
            value: Message value (dict)
            key: Optional message key (string)
            partition: Optional partition number
            headers: Optional message headers

        Raises:
            RuntimeError: If producer is not started
            KafkaProducerError: If sending fails
        """
        # Serialize value to JSON bytes
        value_bytes = json.dumps(value, ensure_ascii=False).encode("utf-8")

        # Serialize key to bytes if provided
        key_bytes = key.encode("utf-8") if key else None

        await self.send(
            topic=topic,
            value=value_bytes,
            key=key_bytes,
            partition=partition,
            headers=headers,
        )

    async def send_batch(self, messages: List[Dict[str, bytes]]) -> None:
        """Send multiple messages in batch.

        Args:
            messages: List of message dicts with 'topic', 'value', 'key', etc.

        Raises:
            RuntimeError: If producer is not started
            KafkaProducerError: If sending fails

        Example:
            ```python
            await producer.send_batch([
                {"topic": "analytics", "value": b"data1", "key": b"key1"},
                {"topic": "analytics", "value": b"data2", "key": b"key2"},
            ])
            ```
        """
        if not self.producer or not self._running:
            raise RuntimeError("Producer not started. Call start() first.")

        try:
            for msg in messages:
                topic = msg.get("topic")
                value = msg.get("value")
                key = msg.get("key")
                partition = msg.get("partition")
                headers = msg.get("headers")

                if not topic or value is None:
                    logger.warning(f"Skipping invalid message: {msg}")
                    continue

                await self.send(
                    topic=topic,
                    value=value,
                    key=key,
                    partition=partition,
                    headers=headers,
                )

            logger.info(f"Sent batch of {len(messages)} messages")

        except Exception as e:
            logger.error(f"Failed to send batch: {e}")
            raise KafkaProducerError(f"Batch send failed: {e}") from e

    def is_running(self) -> bool:
        """Check if producer is running.

        Returns:
            bool: True if running, False otherwise
        """
        return self._running and self.producer is not None


__all__ = [
    "IKafkaProducer",
    "KafkaProducer",
    "KafkaProducerError",
]

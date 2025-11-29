"""RabbitMQ client infrastructure for message consumption.

This module provides a robust RabbitMQ client that handles connection management,
message consumption with QoS, and graceful shutdown.

Note: Requires aio-pika package. Install with: pip install aio-pika
"""

import asyncio
from typing import Callable, Optional, Any, TYPE_CHECKING

try:
    import aio_pika  # type: ignore
    from aio_pika import Message, IncomingMessage  # type: ignore
    from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel  # type: ignore

    AIO_PIKA_AVAILABLE = True
except ImportError:
    AIO_PIKA_AVAILABLE = False
    # Type stubs for when aio_pika is not available
    if TYPE_CHECKING:
        from aio_pika import IncomingMessage  # type: ignore
        from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel  # type: ignore
    else:
        AbstractRobustConnection = Any
        AbstractRobustChannel = Any
        IncomingMessage = Any

from core.logger import logger


class RabbitMQClient:
    """RabbitMQ client for robust message consumption.

    This class manages the lifecycle of RabbitMQ connections and provides
    methods for consuming messages with proper QoS settings.

    Attributes:
        rabbitmq_url: Connection URL for RabbitMQ
        queue_name: Name of the queue to consume from
        prefetch_count: Number of messages to prefetch (QoS setting)
        connection: Active RabbitMQ connection
        channel: Active RabbitMQ channel
    """

    def __init__(
        self, rabbitmq_url: str, queue_name: str = "analytics_queue", prefetch_count: int = 1
    ):
        """Initialize RabbitMQ client.

        Args:
            rabbitmq_url: RabbitMQ connection URL (e.g., 'amqp://guest:guest@localhost/')
            queue_name: Queue to consume messages from
            prefetch_count: Maximum number of unacknowledged messages (QoS)

        Raises:
            ImportError: If aio-pika is not installed
        """
        if not AIO_PIKA_AVAILABLE:
            raise ImportError(
                "aio-pika is required for RabbitMQ support. " "Install with: pip install aio-pika"
            )

        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.prefetch_count = prefetch_count

        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractRobustChannel] = None

        logger.info(f"RabbitMQ client initialized (queue={queue_name}, prefetch={prefetch_count})")

    async def connect(self) -> None:
        """Establish robust connection to RabbitMQ.

        Creates a connection and channel with automatic reconnection support.

        Raises:
            Exception: If connection fails
        """
        try:
            logger.info(f"Connecting to RabbitMQ at {self.rabbitmq_url}...")

            # Create robust connection (auto-reconnects)
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)

            logger.info("RabbitMQ connection established")

            # Create channel
            self.channel = await self.connection.channel()

            # Set QoS - limit concurrent message processing
            await self.channel.set_qos(prefetch_count=self.prefetch_count)

            logger.info(f"RabbitMQ channel created (QoS prefetch_count={self.prefetch_count})")

            # Declare queue (idempotent - creates if doesn't exist)
            queue = await self.channel.declare_queue(
                self.queue_name, durable=True  # Survive broker restarts
            )

            logger.info(f"Queue '{self.queue_name}' declared (durable=True)")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            logger.exception("RabbitMQ connection error details:")
            raise

    async def close(self) -> None:
        """Close RabbitMQ connection gracefully.

        Closes the channel and connection if they exist.
        """
        try:
            logger.info("Closing RabbitMQ connection...")

            if self.channel and not self.channel.is_closed:
                await self.channel.close()
                logger.info("RabbitMQ channel closed")

            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("RabbitMQ connection closed")

        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
            logger.exception("RabbitMQ close error details:")

    async def consume(self, message_handler: Callable[[IncomingMessage], Any]) -> None:
        """Start consuming messages from the queue.

        This method runs indefinitely, processing messages as they arrive.

        Args:
            message_handler: Async callable to process incoming messages.
                             Should accept IncomingMessage and handle ack/nack.

        Raises:
            RuntimeError: If not connected to RabbitMQ
            Exception: If consumption fails

        Example:
            ```python
            async def handle_message(message: IncomingMessage):
                async with message.process():
                    data = json.loads(message.body)
                    # Process data...
                    # Message auto-acked if no exception

            await client.consume(handle_message)
            ```
        """
        if not self.connection or not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        try:
            logger.info(f"Starting message consumption from queue '{self.queue_name}'...")

            # Get queue
            queue = await self.channel.get_queue(self.queue_name)

            # Start consuming
            await queue.consume(message_handler)

            logger.info(f"Consumer started successfully (queue={self.queue_name})")

            # Keep consuming until interrupted
            logger.info("Waiting for messages. To exit press CTRL+C")

        except Exception as e:
            logger.error(f"Error during message consumption: {e}")
            logger.exception("Consumption error details:")
            raise

    def is_connected(self) -> bool:
        """Check if connected to RabbitMQ.

        Returns:
            bool: True if connected, False otherwise
        """
        return (
            self.connection is not None
            and not self.connection.is_closed
            and self.channel is not None
            and not self.channel.is_closed
        )

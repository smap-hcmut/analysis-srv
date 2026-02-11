from __future__ import annotations

from typing import Awaitable, Callable, Optional, Protocol, runtime_checkable

import aio_pika
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection
from loguru import logger

from .constant import *
from .type import RabbitMQConfig


@runtime_checkable
class IMessageConsumer(Protocol):
    """Protocol defining the message consumer interface."""

    async def connect(self) -> None:
        """Establish connection to message broker."""
        ...

    async def close(self) -> None:
        """Close connection gracefully."""
        ...

    async def consume(
        self, message_handler: Callable[[IncomingMessage], Awaitable[None]]
    ) -> None:
        """Start consuming messages from the queue."""
        ...

    def is_connected(self) -> bool:
        """Check if connected to message broker."""
        ...


class RabbitMQClient(IMessageConsumer):
    """RabbitMQ client for robust message consumption.

    This class manages the lifecycle of RabbitMQ connections and provides
    methods for consuming messages with proper QoS settings.

    Attributes:
        config: RabbitMQ configuration
        connection: Active RabbitMQ connection
        channel: Active RabbitMQ channel
    """

    def __init__(self, config: RabbitMQConfig):
        """Initialize RabbitMQ client with configuration.

        Args:
            config: RabbitMQ configuration

        Raises:
            ImportError: If aio-pika is not installed
        """
        self.config = config
        self.connection: Optional[AbstractRobustConnection] = None
        self.channel: Optional[AbstractRobustChannel] = None

        logger.info(
            f"RabbitMQ client initialized (queue={config.queue_name}, prefetch={config.prefetch_count})"
        )

    async def connect(self) -> None:
        """Establish robust connection to RabbitMQ.

        Creates a connection and channel with automatic reconnection support.
        Optionally binds queue to an exchange with routing key from config.

        Raises:
            Exception: If connection fails
        """
        try:
            logger.info(f"Connecting to RabbitMQ at {self.config.url}...")

            # Create robust connection (auto-reconnects)
            self.connection = await aio_pika.connect_robust(self.config.url)

            logger.info("RabbitMQ connection established")

            # Create channel
            self.channel = await self.connection.channel()

            # Set QoS - limit concurrent message processing
            await self.channel.set_qos(prefetch_count=self.config.prefetch_count)

            logger.info(
                f"RabbitMQ channel created (QoS prefetch_count={self.config.prefetch_count})"
            )

            # Declare queue (idempotent - creates if doesn't exist)
            queue = await self.channel.declare_queue(
                self.config.queue_name, durable=True  # Survive broker restarts
            )

            logger.info(f"Queue '{self.config.queue_name}' declared (durable=True)")

            # Bind to exchange if specified in config
            if self.config.exchange_name and self.config.routing_key:
                # Declare exchange (topic type for routing key patterns)
                exchange = await self.channel.declare_exchange(
                    self.config.exchange_name,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                logger.info(
                    f"Exchange '{self.config.exchange_name}' declared (type=topic, durable=True)"
                )

                # Bind queue to exchange with routing key
                await queue.bind(exchange, routing_key=self.config.routing_key)
                logger.info(
                    f"Queue '{self.config.queue_name}' bound to exchange '{self.config.exchange_name}' "
                    f"with routing_key='{self.config.routing_key}'"
                )

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

    async def consume(
        self, message_handler: Callable[[IncomingMessage], Awaitable[None]]
    ) -> None:
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
            logger.info(
                f"Starting message consumption from queue '{self.config.queue_name}'..."
            )

            # Get queue
            queue = await self.channel.get_queue(self.config.queue_name)

            # Start consuming
            await queue.consume(message_handler)

            logger.info(
                f"Consumer started successfully (queue={self.config.queue_name})"
            )

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

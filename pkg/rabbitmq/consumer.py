from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

import aio_pika
from aio_pika import IncomingMessage
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection
from loguru import logger

from .interface import IMessageConsumer
from .constant import *
from .type import RabbitMQConfig


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
        self._consume_future: Optional[asyncio.Future] = None

    async def connect(self) -> None:
        """Establish robust connection to RabbitMQ.

        Creates a connection and channel with automatic reconnection support.
        Optionally binds queue to an exchange with routing key from config.

        Raises:
            Exception: If connection fails
        """
        try:
            # Create robust connection (auto-reconnects)
            self.connection = await aio_pika.connect_robust(self.config.url)

            # Create channel
            self.channel = await self.connection.channel()

            # Set QoS - limit concurrent message processing
            await self.channel.set_qos(prefetch_count=self.config.prefetch_count)

            # Declare queue (idempotent - creates if doesn't exist)
            queue = await self.channel.declare_queue(
                self.config.queue_name, durable=True  # Survive broker restarts
            )

            # Bind to exchange if specified in config
            if self.config.exchange_name and self.config.routing_key:
                # Declare exchange (topic type for routing key patterns)
                exchange = await self.channel.declare_exchange(
                    self.config.exchange_name,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                # Bind queue to exchange with routing key
                await queue.bind(exchange, routing_key=self.config.routing_key)
                
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

            # Cancel consume future to stop blocking
            if self._consume_future and not self._consume_future.done():
                self._consume_future.cancel()

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
        """
        if not self.connection or not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        try:
            # Get queue
            queue = await self.channel.get_queue(self.config.queue_name)

            # Start consuming
            await queue.consume(message_handler)

            logger.info("Consumer started, waiting for messages...")

            # Block forever to keep consuming (can be cancelled)
            self._consume_future = asyncio.Future()
            try:
                await self._consume_future
            except asyncio.CancelledError:
                logger.info("Consumer stopped")
                raise

        except asyncio.CancelledError:
            # Normal shutdown
            pass
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

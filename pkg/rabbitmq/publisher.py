from __future__ import annotations

import json
from typing import Optional, Protocol, Union, runtime_checkable

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractRobustChannel, AbstractExchange
from loguru import logger

from .constant import *
from .type import PublisherConfig, MessagePayload


@runtime_checkable
class IMessagePublisher(Protocol):
    """Protocol defining the message publisher interface."""

    async def setup(self) -> None:
        """Setup publisher (declare exchange, etc.)."""
        ...

    async def publish(self, message: dict, routing_key: Optional[str] = None) -> None:
        """Publish a message to the exchange."""
        ...

    def is_ready(self) -> bool:
        """Check if publisher is ready to publish."""
        ...


class RabbitMQPublisherError(Exception):
    """Base exception for publisher operations."""

    pass


class RabbitMQPublisher(IMessagePublisher):
    """Publisher for sending analyze results to Collector service.

    This class manages publishing of analyze result messages to RabbitMQ.
    It shares the connection with the consumer but uses a separate channel.

    Attributes:
        channel: RabbitMQ channel for publishing
        config: Publisher configuration
        exchange: Declared exchange for result messages
    """

    def __init__(self, channel: AbstractRobustChannel, config: PublisherConfig):
        """Initialize publisher with a RabbitMQ channel and configuration.

        Args:
            channel: aio-pika channel (can be shared or dedicated)
            config: Publisher configuration

        Raises:
            ImportError: If aio-pika is not installed
        """
        self.channel = channel
        self.config = config
        self.exchange: Optional[AbstractExchange] = None
        self._is_setup = False

        logger.info(
            f"RabbitMQ publisher initialized (exchange={config.exchange_name}, routing_key={config.routing_key})"
        )

    async def setup(self) -> None:
        """Declare exchange for publishing.

        This method is idempotent - calling it multiple times is safe.
        The exchange is declared as durable topic exchange.

        Raises:
            RabbitMQPublisherError: If exchange declaration fails.
        """
        if self._is_setup:
            logger.debug("Publisher already setup, skipping")
            return

        try:
            logger.info(
                f"Declaring exchange '{self.config.exchange_name}' for result publishing..."
            )

            self.exchange = await self.channel.declare_exchange(
                self.config.exchange_name,
                ExchangeType.TOPIC,
                durable=self.config.durable,
            )

            self._is_setup = True
            logger.info(
                f"Exchange '{self.config.exchange_name}' declared successfully "
                f"(type=topic, durable={self.config.durable})"
            )

        except Exception as exc:
            logger.error(
                f"Failed to declare exchange '{self.config.exchange_name}': {exc}"
            )
            raise RabbitMQPublisherError(f"Failed to setup publisher: {exc}") from exc

    async def publish(
        self,
        message: dict,
        routing_key: Optional[str] = None,
    ) -> None:
        """Publish a message to the exchange.

        Args:
            message: Dictionary to serialize and publish.
            routing_key: Optional routing key override.

        Raises:
            RabbitMQPublisherError: If publishing fails or publisher not setup.
        """
        if not self._is_setup or self.exchange is None:
            raise RabbitMQPublisherError(ERROR_PUBLISHER_NOT_SETUP)

        key = routing_key or self.config.routing_key

        try:
            body = json.dumps(message, ensure_ascii=False).encode("utf-8")

            await self.exchange.publish(
                Message(
                    body,
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                ),
                routing_key=key,
            )

            logger.debug(
                f"Published message to exchange={self.config.exchange_name}, routing_key={key}, size={len(body)} bytes"
            )

        except Exception as exc:
            logger.error(
                f"Failed to publish message to exchange={self.config.exchange_name}, routing_key={key}: {exc}"
            )
            raise RabbitMQPublisherError(f"Failed to publish message: {exc}") from exc

    async def publish_analyze_result(
        self,
        payload: Union[MessagePayload, dict],
        routing_key: Optional[str] = None,
    ) -> None:
        """Publish an analyze result payload to Collector.

        Accepts AnalyzeResultPayload (flat format) or dictionary.
        Validates that project_id is non-empty before publishing.

        Args:
            payload: MessagePayload instance (with to_dict method) or flat dictionary.
            routing_key: Optional routing key override.

        Raises:
            RabbitMQPublisherError: If project_id is empty or publishing fails.
        """
        # Handle both dataclass and dict
        if hasattr(payload, "to_dict"):
            message_dict = payload.to_dict()
            project_id = getattr(payload, "project_id", None)
        elif isinstance(payload, dict):
            message_dict = payload
            # Handle both flat and nested (legacy) formats
            if "payload" in payload:
                project_id = payload.get("payload", {}).get("project_id")
            else:
                project_id = payload.get("project_id")
        else:
            raise RabbitMQPublisherError(
                ERROR_INVALID_MESSAGE_TYPE.format(type=type(payload).__name__)
            )

        # Validate project_id is non-empty (required by Collector contract)
        if not project_id:
            raise RabbitMQPublisherError(ERROR_PROJECT_ID_REQUIRED)

        await self.publish(message_dict, routing_key)

        # Log summary for monitoring (flat format)
        job_id = message_dict.get("job_id")
        batch_size = message_dict.get("batch_size", 0)
        success_count = message_dict.get("success_count", 0)
        error_count = message_dict.get("error_count", 0)
        logger.info(
            f"Published analyze result: project_id={project_id}, job_id={job_id}, "
            f"batch_size={batch_size}, success_count={success_count}, error_count={error_count}"
        )

    def is_ready(self) -> bool:
        """Check if publisher is ready to publish.

        Returns:
            True if setup() has been called successfully.
        """
        return self._is_setup and self.exchange is not None

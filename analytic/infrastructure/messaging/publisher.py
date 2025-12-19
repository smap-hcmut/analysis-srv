"""RabbitMQ publisher for sending analyze results to Collector service.

This module provides a publisher that sends batch analysis results
to the Collector service via RabbitMQ.

Note: Requires aio-pika package. Install with: pip install aio-pika
"""

from __future__ import annotations

import json
from typing import Any, Optional, TYPE_CHECKING

try:
    import aio_pika
    from aio_pika import Message, DeliveryMode, ExchangeType
    from aio_pika.abc import AbstractRobustChannel, AbstractExchange

    AIO_PIKA_AVAILABLE = True
except ImportError:
    AIO_PIKA_AVAILABLE = False
    if TYPE_CHECKING:
        from aio_pika.abc import AbstractRobustChannel, AbstractExchange
    else:
        AbstractRobustChannel = Any
        AbstractExchange = Any

from core.logger import logger
from core.config import settings


class RabbitMQPublisherError(Exception):
    """Base exception for publisher operations."""

    pass


class RabbitMQPublisher:
    """Publisher for sending analyze results to Collector service.

    This class manages publishing of analyze result messages to RabbitMQ.
    It shares the connection with the consumer but uses a separate channel.

    Attributes:
        channel: RabbitMQ channel for publishing.
        exchange: Declared exchange for result messages.
        exchange_name: Name of the exchange.
        routing_key: Default routing key for messages.
    """

    def __init__(
        self,
        channel: AbstractRobustChannel,
        exchange_name: Optional[str] = None,
        routing_key: Optional[str] = None,
    ):
        """Initialize publisher with a RabbitMQ channel.

        Args:
            channel: aio-pika channel (can be shared or dedicated).
            exchange_name: Exchange name for publishing. Defaults to config value.
            routing_key: Default routing key. Defaults to config value.

        Raises:
            ImportError: If aio-pika is not installed.
        """
        if not AIO_PIKA_AVAILABLE:
            raise ImportError(
                "aio-pika is required for RabbitMQ support. " "Install with: pip install aio-pika"
            )

        self.channel = channel
        self.exchange_name = exchange_name or settings.publish_exchange
        self.routing_key = routing_key or settings.publish_routing_key
        self.exchange: Optional[AbstractExchange] = None
        self._is_setup = False

        logger.info(
            f"RabbitMQ publisher initialized (exchange={self.exchange_name}, routing_key={self.routing_key})"
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
            logger.info(f"Declaring exchange '{self.exchange_name}' for result publishing...")

            self.exchange = await self.channel.declare_exchange(
                self.exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )

            self._is_setup = True
            logger.info(
                f"Exchange '{self.exchange_name}' declared successfully (type=topic, durable=True)"
            )

        except Exception as exc:
            logger.error(f"Failed to declare exchange '{self.exchange_name}': {exc}")
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
            raise RabbitMQPublisherError("Publisher not setup. Call setup() first.")

        key = routing_key or self.routing_key

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
                f"Published message to exchange={self.exchange_name}, routing_key={key}, size={len(body)} bytes"
            )

        except Exception as exc:
            logger.error(
                f"Failed to publish message to exchange={self.exchange_name}, routing_key={key}: {exc}"
            )
            raise RabbitMQPublisherError(f"Failed to publish message: {exc}") from exc

    async def publish_analyze_result(
        self,
        payload: Any,
        routing_key: Optional[str] = None,
    ) -> None:
        """Publish an analyze result payload to Collector.

        Accepts AnalyzeResultPayload (flat format) or dictionary.
        Validates that project_id is non-empty before publishing.

        Args:
            payload: AnalyzeResultPayload instance or flat dictionary.
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
                f"Invalid message type: {type(payload).__name__}. "
                "Expected AnalyzeResultPayload or dict."
            )

        # Validate project_id is non-empty (required by Collector contract)
        if not project_id:
            raise RabbitMQPublisherError(
                "project_id is required for publishing analyze results. "
                "Collector will reject messages without project_id."
            )

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

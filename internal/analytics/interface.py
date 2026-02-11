from typing import Protocol, runtime_checkable
from aio_pika import IncomingMessage


@runtime_checkable
class IAnalyticsHandler(Protocol):
    """Protocol for analytics message handler."""

    async def handle(self, message: IncomingMessage) -> None:
        """Handle analytics message.

        Args:
            message: Incoming RabbitMQ message
        """
        ...


@runtime_checkable
class IAnalyticsUseCase(Protocol):
    """Protocol for analytics business logic."""

    async def process_analytics(self, data: dict) -> None:
        """Process analytics data.

        Args:
            data: Parsed message data
        """
        ...


__all__ = ["IAnalyticsHandler", "IAnalyticsUseCase"]

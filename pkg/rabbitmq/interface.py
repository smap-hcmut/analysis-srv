"""Interfaces for RabbitMQ message operations."""

from typing import Awaitable, Callable, Optional, Protocol, runtime_checkable

from aio_pika import IncomingMessage


@runtime_checkable
class IMessageConsumer(Protocol):
    """Protocol for message consumer operations."""

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


@runtime_checkable
class IMessagePublisher(Protocol):
    """Protocol for message publisher operations."""

    async def setup(self) -> None:
        """Setup publisher (declare exchange, etc.)."""
        ...

    async def publish(self, message: dict, routing_key: Optional[str] = None) -> None:
        """Publish a message to the exchange."""
        ...

    def is_ready(self) -> bool:
        """Check if publisher is ready to publish."""
        ...


__all__ = ["IMessageConsumer", "IMessagePublisher"]

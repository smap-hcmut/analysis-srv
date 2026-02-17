"""Interfaces for Kafka operations."""

from typing import Callable, Dict, List, Optional, Awaitable, Protocol, runtime_checkable

from .type import KafkaMessage


@runtime_checkable
class IKafkaConsumer(Protocol):
    """Protocol for Kafka consumer operations."""

    async def start(self) -> None:
        """Start the consumer and connect to Kafka."""
        ...

    async def stop(self) -> None:
        """Stop the consumer gracefully."""
        ...

    async def consume(
        self, message_handler: Callable[[KafkaMessage], Awaitable[None]]
    ) -> None:
        """Start consuming messages from subscribed topics."""
        ...

    async def commit(self) -> None:
        """Manually commit offsets."""
        ...

    def is_running(self) -> bool:
        """Check if consumer is running."""
        ...


@runtime_checkable
class IKafkaProducer(Protocol):
    """Protocol for Kafka producer operations."""

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


__all__ = ["IKafkaConsumer", "IKafkaProducer"]

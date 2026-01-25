"""Message queue interface - Abstract base class for message queue operations."""

from abc import ABC, abstractmethod
from typing import Callable, Any, Dict


class IMessageQueue(ABC):
    """Interface for message queue operations (RabbitMQ, Redis, etc.)."""

    @abstractmethod
    async def publish(
        self,
        queue: str,
        message: Dict[str, Any],
        priority: int = 0,
    ) -> bool:
        """Publish a message to a queue."""
        pass

    @abstractmethod
    async def consume(
        self,
        queue: str,
        callback: Callable[[Dict[str, Any]], None],
        prefetch_count: int = 1,
    ) -> None:
        """Consume messages from a queue."""
        pass

    @abstractmethod
    async def ack(self, delivery_tag: int) -> None:
        """Acknowledge a message."""
        pass

    @abstractmethod
    async def nack(self, delivery_tag: int, requeue: bool = True) -> None:
        """Negative acknowledge a message."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass

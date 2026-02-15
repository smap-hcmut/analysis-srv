from dataclasses import dataclass
from typing import Optional, Protocol
from .constant import *


class MessagePayload(Protocol):
    """Protocol for message payloads that can be converted to dict."""

    def to_dict(self) -> dict:
        """Convert payload to dictionary."""
        ...


@dataclass
class RabbitMQConfig:
    """RabbitMQ connection configuration."""

    url: str
    queue_name: str = DEFAULT_QUEUE_NAME
    prefetch_count: int = DEFAULT_PREFETCH_COUNT
    exchange_name: Optional[str] = None
    routing_key: Optional[str] = None

    def __post_init__(self):
        """Validate configuration."""
        if not self.url or not self.url.strip():
            raise ValueError(ERROR_URL_EMPTY)

        if not self.queue_name or not self.queue_name.strip():
            raise ValueError(ERROR_QUEUE_NAME_EMPTY)

        if self.prefetch_count <= 0:
            raise ValueError(
                ERROR_PREFETCH_COUNT_POSITIVE.format(count=self.prefetch_count)
            )


@dataclass
class PublisherConfig:
    """RabbitMQ publisher configuration."""

    exchange_name: str
    routing_key: str
    durable: bool = DEFAULT_DURABLE

    def __post_init__(self):
        """Validate configuration."""
        if not self.exchange_name or not self.exchange_name.strip():
            raise ValueError(ERROR_EXCHANGE_NAME_EMPTY)

        if not self.routing_key or not self.routing_key.strip():
            raise ValueError(ERROR_ROUTING_KEY_EMPTY)

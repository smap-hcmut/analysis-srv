from dataclasses import dataclass, field
from typing import Optional, List, Dict
from .constant import *


class KafkaConsumerError(Exception):
    """Base exception for Kafka consumer operations."""

    pass


@dataclass
class KafkaConsumerConfig:
    """Kafka consumer configuration.

    Attributes:
        bootstrap_servers: Kafka broker addresses (e.g., 'localhost:9092')
        topics: List of topics to subscribe to
        group_id: Consumer group ID
        auto_offset_reset: Where to start reading ('earliest' or 'latest')
        enable_auto_commit: Whether to auto-commit offsets
        max_poll_records: Maximum records to fetch per poll
        session_timeout_ms: Session timeout in milliseconds
        client_id: Optional client identifier
    """

    bootstrap_servers: str
    topics: List[str]
    group_id: str
    auto_offset_reset: str = DEFAULT_AUTO_OFFSET_RESET
    enable_auto_commit: bool = DEFAULT_ENABLE_AUTO_COMMIT
    max_poll_records: int = DEFAULT_MAX_POLL_RECORDS
    session_timeout_ms: int = DEFAULT_SESSION_TIMEOUT_MS
    client_id: Optional[str] = None

    def __post_init__(self):
        """Validate configuration."""
        if not self.bootstrap_servers or not self.bootstrap_servers.strip():
            raise ValueError(ERROR_BOOTSTRAP_SERVERS_EMPTY)

        if not self.topics or len(self.topics) == 0:
            raise ValueError(ERROR_TOPICS_EMPTY)

        if not self.group_id or not self.group_id.strip():
            raise ValueError(ERROR_GROUP_ID_EMPTY)

        if self.auto_offset_reset not in VALID_AUTO_OFFSET_RESET:
            raise ValueError(
                ERROR_INVALID_AUTO_OFFSET_RESET.format(value=self.auto_offset_reset)
            )

        if self.max_poll_records <= 0:
            raise ValueError(
                ERROR_INVALID_MAX_POLL_RECORDS.format(value=self.max_poll_records)
            )

        if self.session_timeout_ms <= 0:
            raise ValueError(
                ERROR_INVALID_SESSION_TIMEOUT.format(value=self.session_timeout_ms)
            )


@dataclass
class KafkaProducerConfig:
    """Kafka producer configuration.

    Attributes:
        bootstrap_servers: Kafka broker addresses (e.g., 'localhost:9092')
        acks: Number of acknowledgments ('all', 1, or 0)
        compression_type: Compression algorithm ('gzip', 'snappy', 'lz4', 'zstd', or None)
        max_batch_size: Maximum batch size in bytes
        linger_ms: Time to wait before sending batch
        client_id: Optional client identifier
        enable_idempotence: Whether to enable idempotent producer
    """

    bootstrap_servers: str
    acks: str = DEFAULT_ACKS
    compression_type: Optional[str] = DEFAULT_COMPRESSION_TYPE
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE
    linger_ms: int = DEFAULT_LINGER_MS
    client_id: Optional[str] = None
    enable_idempotence: bool = DEFAULT_ENABLE_IDEMPOTENCE

    def __post_init__(self):
        """Validate configuration."""
        if not self.bootstrap_servers or not self.bootstrap_servers.strip():
            raise ValueError(ERROR_BOOTSTRAP_SERVERS_EMPTY)

        if self.acks not in VALID_ACKS:
            raise ValueError(ERROR_INVALID_ACKS.format(value=self.acks))

        if (
            self.compression_type
            and self.compression_type not in VALID_COMPRESSION_TYPES
        ):
            raise ValueError(
                ERROR_INVALID_COMPRESSION_TYPE.format(value=self.compression_type)
            )

        if self.max_batch_size <= 0:
            raise ValueError(
                ERROR_INVALID_MAX_BATCH_SIZE.format(value=self.max_batch_size)
            )

        if self.linger_ms < 0:
            raise ValueError(ERROR_INVALID_LINGER_MS.format(value=self.linger_ms))


@dataclass
class KafkaMessage:
    """Kafka message data model.

    Attributes:
        topic: Topic name
        partition: Partition number
        offset: Message offset
        key: Message key (optional)
        value: Message value (bytes)
        timestamp: Message timestamp
        headers: Message headers
    """

    topic: str
    partition: int
    offset: int
    value: bytes
    key: Optional[bytes] = None
    timestamp: Optional[int] = None
    headers: Dict[str, bytes] = field(default_factory=dict)


__all__ = [
    "KafkaConsumerConfig",
    "KafkaProducerConfig",
    "KafkaConsumerError",
    "KafkaMessage",
]

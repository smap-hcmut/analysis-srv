"""Delivery layer DTOs for analytics domain.

Convention: Delivery DTOs are DECOUPLED from domain types.
These structs represent the wire format (message queue payloads).
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DataCollectedMessage:
    """DTO for incoming data.collected event from RabbitMQ.

    This is the wire format — decoupled from domain Input type.
    """

    event_id: str = ""
    event_type: str = ""
    timestamp: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostPayload:
    """DTO for post data within the message payload."""

    meta: dict[str, Any] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)
    interaction: dict[str, Any] = field(default_factory=dict)
    author: dict[str, Any] = field(default_factory=dict)
    comments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EventPayloadMetadata:
    """DTO for event-level metadata within the payload."""

    project_id: Optional[str] = None
    job_id: Optional[str] = None
    batch_index: Optional[int] = None
    content_count: Optional[int] = None
    platform: Optional[str] = None
    task_type: Optional[str] = None
    brand_name: Optional[str] = None
    keyword: Optional[str] = None
    minio_path: Optional[str] = None


__all__ = [
    "DataCollectedMessage",
    "PostPayload",
    "EventPayloadMetadata",
]

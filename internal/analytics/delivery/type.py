from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DataCollectedMessage:
    event_id: str = ""
    event_type: str = ""
    timestamp: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostPayload:
    meta: dict[str, Any] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)
    interaction: dict[str, Any] = field(default_factory=dict)
    author: dict[str, Any] = field(default_factory=dict)
    comments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EventPayloadMetadata:
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    batch_index: Optional[int] = None
    content_count: Optional[int] = None
    platform: Optional[str] = None
    task_type: Optional[str] = None
    brand_name: Optional[str] = None
    keyword: Optional[str] = None
    minio_path: Optional[str] = None


@dataclass
class UAPMessage:
    uap_version: str = ""
    event_id: str = ""
    raw_body: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "DataCollectedMessage",
    "PostPayload",
    "EventPayloadMetadata",
    "UAPMessage",
]

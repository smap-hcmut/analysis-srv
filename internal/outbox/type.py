"""outbox/type.py — OutboxRecord and OutboxStatus."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

OutboxStatus = Literal["pending", "sent", "failed"]


@dataclass
class OutboxRecord:
    """A single message pending delivery to Kafka."""

    id: str
    run_id: str
    topic: str
    payload: dict
    status: OutboxStatus = "pending"
    created_at: datetime | None = None
    sent_at: datetime | None = None
    error: str | None = None

    @classmethod
    def new(cls, run_id: str, topic: str, payload: dict) -> "OutboxRecord":
        """Create a new pending outbox record with a generated UUID."""
        return cls(id=str(uuid.uuid4()), run_id=run_id, topic=topic, payload=payload)


@dataclass
class RelayResult:
    """Summary of one relay cycle."""

    attempted: int = 0
    sent: int = 0
    failed: int = 0


__all__ = ["OutboxStatus", "OutboxRecord", "RelayResult"]

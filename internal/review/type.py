"""review/type.py — ReviewItem, ReviewStatus, ReviewDecision."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

ReviewStatus = Literal["pending", "approved", "rejected", "skipped"]
ReviewDecision = Literal["approve", "reject", "skip"]


@dataclass
class ReviewItem:
    """A single enrichment fact queued for human review.

    Fields
    ------
    id            : Unique item identifier (UUID string).
    run_id        : The pipeline run that produced this fact.
    project_id    : Project context.
    mention_id    : The source mention document.
    fact_type     : The enrichment category (entity, topic, intent, …).
    fact_payload  : Serialised fact (dict — JSON-safe).
    confidence    : Model confidence score at inference time.
    status        : Current queue status.
    created_at    : UTC timestamp of enqueueing.
    resolved_at   : UTC timestamp of resolution (None if still pending).
    resolution_note: Optional reviewer note.
    """

    id: str
    run_id: str
    project_id: str
    mention_id: str
    fact_type: str
    fact_payload: dict
    confidence: float
    status: ReviewStatus = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    resolution_note: str | None = None

    @classmethod
    def new(
        cls,
        run_id: str,
        project_id: str,
        mention_id: str,
        fact_type: str,
        fact_payload: dict,
        confidence: float,
    ) -> "ReviewItem":
        """Create a new pending ReviewItem with a generated UUID."""
        return cls(
            id=str(uuid.uuid4()),
            run_id=run_id,
            project_id=project_id,
            mention_id=mention_id,
            fact_type=fact_type,
            fact_payload=fact_payload,
            confidence=confidence,
        )

    def is_pending(self) -> bool:
        return self.status == "pending"

    def is_resolved(self) -> bool:
        return self.status in ("approved", "rejected", "skipped")


@dataclass
class ReviewQueueSummary:
    """Aggregate counts for a project's review queue."""

    project_id: str
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    skipped: int = 0


__all__ = [
    "ReviewStatus",
    "ReviewDecision",
    "ReviewItem",
    "ReviewQueueSummary",
]

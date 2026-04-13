"""review/constant.py — review queue thresholds and limits."""

from __future__ import annotations

# Confidence score below which an enrichment fact is queued for human review
LOW_CONFIDENCE_THRESHOLD: float = 0.65

# Maximum items returned by get_pending_items() when limit is not specified
DEFAULT_FETCH_LIMIT: int = 100

# Maximum items allowed in the pending queue per project before oldest are dropped
MAX_QUEUE_SIZE: int = 5_000

# Fact types that are eligible for review queueing
REVIEWABLE_FACT_TYPES: frozenset[str] = frozenset(
    {
        "entity",
        "topic",
        "intent",
        "aspect",
        "issue",
        "stance",
    }
)

__all__ = [
    "LOW_CONFIDENCE_THRESHOLD",
    "DEFAULT_FETCH_LIMIT",
    "MAX_QUEUE_SIZE",
    "REVIEWABLE_FACT_TYPES",
]

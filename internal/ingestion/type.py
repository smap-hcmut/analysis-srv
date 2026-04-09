"""Ingestion module types.

`IngestedBatchBundle` lives in `internal.pipeline.type` and is re-exported here
for convenience.  The ingestion module adds lightweight stat tracking.
"""

from dataclasses import dataclass, field

# Re-export the canonical bundle type so callers can import from one place.
from internal.pipeline.type import IngestedBatchBundle


@dataclass
class IngestionStats:
    """Counters produced by the ingestion adapter."""

    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    error_messages: list[str] = field(default_factory=list)


__all__ = ["IngestedBatchBundle", "IngestionStats"]

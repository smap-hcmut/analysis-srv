"""Message types for Analytics Engine result publishing.

This module defines dataclasses for analyze result messages that are
published to Collector service via RabbitMQ.

Message format follows the Collector contract specification in:
document/collector-crawler-contract.md (Section 3: CONTRACT 2)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json


@dataclass
class AnalyzeError:
    """Error information for a failed content item.

    Attributes:
        content_id: ID of the content that failed processing.
                   Use "batch" for batch-level errors (e.g., MinIO fetch failure).
        error: Human-readable error message.
    """

    content_id: str
    error: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class AnalyzeItem:
    """Analysis result for a successfully processed content item.

    Attributes:
        content_id: ID of the analyzed content.
        sentiment: Overall sentiment label (POSITIVE, NEGATIVE, NEUTRAL).
        sentiment_score: Sentiment score from -1.0 to 1.0.
        impact_score: Calculated impact score from 0 to 100.
    """

    content_id: str
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    impact_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"content_id": self.content_id}
        if self.sentiment is not None:
            result["sentiment"] = self.sentiment
        if self.sentiment_score is not None:
            result["sentiment_score"] = self.sentiment_score
        if self.impact_score is not None:
            result["impact_score"] = self.impact_score
        return result


@dataclass
class AnalyzeResultPayload:
    """Flat payload for Collector consumption.

    Message format follows collector-crawler-contract.md Section 3.
    Published as flat JSON with 6 fields only.

    Attributes:
        project_id: Project identifier for correlation (required, non-empty).
        job_id: Job identifier for correlation.
        task_type: Always "analyze_result" for Collector routing.
        batch_size: Total number of items in the batch.
        success_count: Number of successfully processed items.
        error_count: Number of failed items.
    """

    project_id: str  # Required, non-empty for Collector
    job_id: str
    task_type: str = "analyze_result"
    batch_size: int = 0
    success_count: int = 0
    error_count: int = 0
    # Internal-only fields (not serialized to Collector, used for logging/debugging)
    _results: List[AnalyzeItem] = field(default_factory=list, repr=False)
    _errors: List[AnalyzeError] = field(default_factory=list, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to flat dictionary for Collector.

        Returns only the 6 fields required by Collector contract.
        Internal fields (_results, _errors) are excluded.
        """
        return {
            "project_id": self.project_id,
            "job_id": self.job_id,
            "task_type": self.task_type,
            "batch_size": self.batch_size,
            "success_count": self.success_count,
            "error_count": self.error_count,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_bytes(self) -> bytes:
        """Serialize to JSON bytes for RabbitMQ publishing."""
        return self.to_json().encode("utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalyzeResultPayload":
        """Create instance from dictionary.

        Handles both flat format (new) and nested format (legacy).
        """
        # Handle nested format (legacy): extract from payload
        if "payload" in data:
            data = data.get("payload", {})

        results = [
            AnalyzeItem(
                content_id=r.get("content_id", ""),
                sentiment=r.get("sentiment"),
                sentiment_score=r.get("sentiment_score"),
                impact_score=r.get("impact_score"),
            )
            for r in data.get("results", [])
        ]

        errors = [
            AnalyzeError(
                content_id=e.get("content_id", ""),
                error=e.get("error", ""),
            )
            for e in data.get("errors", [])
        ]

        return cls(
            project_id=data.get("project_id") or "",
            job_id=data.get("job_id", ""),
            task_type=data.get("task_type", "analyze_result"),
            batch_size=data.get("batch_size", 0),
            success_count=data.get("success_count", 0),
            error_count=data.get("error_count", 0),
            _results=results,
            _errors=errors,
        )


@dataclass
class AnalyzeResultMessage:
    """Top-level message wrapper for analyze results.

    .. deprecated::
        This class is deprecated. Use AnalyzeResultPayload directly.
        Collector expects flat message format, not nested with 'success' wrapper.

    This wrapper was used for nested format which is incompatible with
    Collector contract. Kept for backward compatibility only.

    Attributes:
        success: True if majority of items succeeded (error_count < batch_size).
        payload: Detailed batch analysis results.
    """

    success: bool
    payload: AnalyzeResultPayload

    def __post_init__(self):
        warnings.warn(
            "AnalyzeResultMessage is deprecated. Use AnalyzeResultPayload directly "
            "for flat message format required by Collector.",
            DeprecationWarning,
            stacklevel=2,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        .. deprecated::
            Returns nested format. Use AnalyzeResultPayload.to_dict() for flat format.
        """
        return {
            "success": self.success,
            "payload": self.payload.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_bytes(self) -> bytes:
        """Serialize to JSON bytes for RabbitMQ publishing."""
        return self.to_json().encode("utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalyzeResultMessage":
        """Create instance from dictionary.

        Handles both nested format (legacy) and flat format (new).
        """
        # Handle flat format (new): wrap in payload
        if "payload" not in data and "project_id" in data:
            payload = AnalyzeResultPayload.from_dict(data)
            return cls(
                success=data.get("success", payload.error_count < payload.batch_size),
                payload=payload,
            )

        # Handle nested format (legacy)
        payload_data = data.get("payload", {})
        payload = AnalyzeResultPayload.from_dict(payload_data)

        return cls(
            success=data.get("success", False),
            payload=payload,
        )


def create_success_result(
    project_id: str,
    job_id: str,
    batch_size: int,
    success_count: int,
    error_count: int,
    results: Optional[List[AnalyzeItem]] = None,
    errors: Optional[List[AnalyzeError]] = None,
) -> AnalyzeResultPayload:
    """Factory function to create a successful batch result payload.

    Args:
        project_id: Project identifier (required, non-empty).
        job_id: Job identifier.
        batch_size: Total items in batch.
        success_count: Successfully processed items.
        error_count: Failed items.
        results: Optional list of success results (internal use only).
        errors: Optional list of error details (internal use only).

    Returns:
        AnalyzeResultPayload with flat structure for Collector.
    """
    return AnalyzeResultPayload(
        project_id=project_id,
        job_id=job_id,
        task_type="analyze_result",
        batch_size=batch_size,
        success_count=success_count,
        error_count=error_count,
        _results=results or [],
        _errors=errors or [],
    )


def create_error_result(
    project_id: str,
    job_id: str,
    batch_size: int,
    error_message: str,
) -> AnalyzeResultPayload:
    """Factory function to create a batch-level error result payload.

    Use this when the entire batch fails (e.g., MinIO fetch error).

    Args:
        project_id: Project identifier (required, non-empty).
        job_id: Job identifier.
        batch_size: Expected items in batch (all marked as failed).
        error_message: Description of the batch-level error.

    Returns:
        AnalyzeResultPayload with flat structure for Collector.
    """
    return AnalyzeResultPayload(
        project_id=project_id,
        job_id=job_id,
        task_type="analyze_result",
        batch_size=batch_size,
        success_count=0,
        error_count=batch_size,
        _results=[],
        _errors=[AnalyzeError(content_id="batch", error=error_message)],
    )

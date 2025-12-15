"""Message types for Analytics Engine result publishing.

This module defines dataclasses for analyze result messages that are
published to Collector service via RabbitMQ.

Message format follows the integration contract in:
document/integration-analytics-service.md
"""

from __future__ import annotations

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
    """Payload containing batch analysis results.

    Attributes:
        project_id: Project identifier for correlation.
        job_id: Job identifier for correlation.
        task_type: Always "analyze_result" for Collector routing.
        batch_size: Total number of items in the batch.
        success_count: Number of successfully processed items.
        error_count: Number of failed items.
        results: List of successful analysis results (optional).
        errors: List of error details (optional).
    """

    project_id: Optional[str]
    job_id: str
    task_type: str = "analyze_result"
    batch_size: int = 0
    success_count: int = 0
    error_count: int = 0
    results: List[AnalyzeItem] = field(default_factory=list)
    errors: List[AnalyzeError] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_id": self.project_id,
            "job_id": self.job_id,
            "task_type": self.task_type,
            "batch_size": self.batch_size,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "results": [r.to_dict() for r in self.results] if self.results else [],
            "errors": [e.to_dict() for e in self.errors] if self.errors else [],
        }


@dataclass
class AnalyzeResultMessage:
    """Top-level message for analyze results.

    This message is published to RabbitMQ exchange `results.inbound`
    with routing key `analyze.result` for Collector consumption.

    Attributes:
        success: True if majority of items succeeded (error_count < batch_size).
        payload: Detailed batch analysis results.
    """

    success: bool
    payload: AnalyzeResultPayload

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        """Create instance from dictionary."""
        payload_data = data.get("payload", {})

        results = [
            AnalyzeItem(
                content_id=r.get("content_id", ""),
                sentiment=r.get("sentiment"),
                sentiment_score=r.get("sentiment_score"),
                impact_score=r.get("impact_score"),
            )
            for r in payload_data.get("results", [])
        ]

        errors = [
            AnalyzeError(
                content_id=e.get("content_id", ""),
                error=e.get("error", ""),
            )
            for e in payload_data.get("errors", [])
        ]

        payload = AnalyzeResultPayload(
            project_id=payload_data.get("project_id"),
            job_id=payload_data.get("job_id", ""),
            task_type=payload_data.get("task_type", "analyze_result"),
            batch_size=payload_data.get("batch_size", 0),
            success_count=payload_data.get("success_count", 0),
            error_count=payload_data.get("error_count", 0),
            results=results,
            errors=errors,
        )

        return cls(
            success=data.get("success", False),
            payload=payload,
        )


def create_success_result(
    project_id: Optional[str],
    job_id: str,
    batch_size: int,
    success_count: int,
    error_count: int,
    results: Optional[List[AnalyzeItem]] = None,
    errors: Optional[List[AnalyzeError]] = None,
) -> AnalyzeResultMessage:
    """Factory function to create a successful batch result message.

    Args:
        project_id: Project identifier.
        job_id: Job identifier.
        batch_size: Total items in batch.
        success_count: Successfully processed items.
        error_count: Failed items.
        results: Optional list of success results.
        errors: Optional list of error details.

    Returns:
        AnalyzeResultMessage with success=True if error_count < batch_size.
    """
    return AnalyzeResultMessage(
        success=error_count < batch_size,
        payload=AnalyzeResultPayload(
            project_id=project_id,
            job_id=job_id,
            task_type="analyze_result",
            batch_size=batch_size,
            success_count=success_count,
            error_count=error_count,
            results=results or [],
            errors=errors or [],
        ),
    )


def create_error_result(
    project_id: Optional[str],
    job_id: str,
    batch_size: int,
    error_message: str,
) -> AnalyzeResultMessage:
    """Factory function to create a batch-level error result message.

    Use this when the entire batch fails (e.g., MinIO fetch error).

    Args:
        project_id: Project identifier.
        job_id: Job identifier.
        batch_size: Expected items in batch (all marked as failed).
        error_message: Description of the batch-level error.

    Returns:
        AnalyzeResultMessage with success=False and batch-level error.
    """
    return AnalyzeResultMessage(
        success=False,
        payload=AnalyzeResultPayload(
            project_id=project_id,
            job_id=job_id,
            task_type="analyze_result",
            batch_size=batch_size,
            success_count=0,
            error_count=batch_size,
            results=[],
            errors=[AnalyzeError(content_id="batch", error=error_message)],
        ),
    )

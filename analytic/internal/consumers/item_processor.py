"""Item processor for batch processing of crawler events.

This module provides utilities for processing individual items from
crawler batches, including success and error handling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from core.logger import logger
from core.constants import categorize_error, ErrorCategory
from repository.analytics_repository import AnalyticsRepository
from repository.crawl_error_repository import CrawlErrorRepository
from utils.id_utils import ensure_string_id, log_id_warnings, validate_post_id


class ItemProcessingResult:
    """Result of processing a single item."""

    def __init__(
        self,
        content_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        impact_score: Optional[float] = None,
    ):
        # Ensure content_id is string to prevent BigInt precision loss
        self.content_id = ensure_string_id(content_id) if content_id else content_id
        self.status = status  # "success" or "error"
        self.error_code = error_code
        self.error_message = error_message
        self.impact_score = impact_score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "status": self.status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "impact_score": self.impact_score,
        }


class BatchProcessingStats:
    """Statistics for batch processing."""

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.error_distribution: dict[str, int] = {}
        self.results: list[ItemProcessingResult] = []

    def add_success(self, result: ItemProcessingResult) -> None:
        """Record a successful item."""
        self.success_count += 1
        self.results.append(result)

    def add_error(self, result: ItemProcessingResult) -> None:
        """Record an error item."""
        self.error_count += 1
        error_code = result.error_code or "UNKNOWN_ERROR"
        self.error_distribution[error_code] = self.error_distribution.get(error_code, 0) + 1
        self.results.append(result)

    @property
    def total_count(self) -> int:
        """Total items processed."""
        return self.success_count + self.error_count

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success_count": self.success_count,
            "error_count": self.error_count,
            "total_count": self.total_count,
            "success_rate": self.success_rate,
            "error_distribution": self.error_distribution,
        }


def is_error_item(item: dict[str, Any]) -> bool:
    """Check if an item is an error item.

    Args:
        item: Item data from batch

    Returns:
        True if item has fetch_status == "error"
    """
    meta = item.get("meta") or {}
    return meta.get("fetch_status") == "error"


def extract_error_info(item: dict[str, Any]) -> dict[str, Any]:
    """Extract error information from an error item.

    Args:
        item: Error item data

    Returns:
        Dictionary with error details
    """
    meta = item.get("meta") or {}

    error_code = meta.get("error_code", "UNKNOWN_ERROR")
    error_category = categorize_error(error_code)

    return {
        "error_code": error_code,
        "error_category": error_category.value,
        "error_message": meta.get("error_message", ""),
        "error_details": meta.get("error_details", {}),
    }


def enrich_item_with_context(
    item: dict[str, Any],
    event_metadata: dict[str, Any],
    project_id: Optional[str],
) -> dict[str, Any]:
    """Enrich item with batch context from event metadata.

    Args:
        item: Original item data
        event_metadata: Event metadata from envelope
        project_id: Extracted project ID

    Returns:
        Enriched item with batch context in meta
    """
    enriched = item.copy()
    meta = enriched.get("meta", {}).copy()

    # Ensure ID is string to prevent BigInt precision loss
    if "id" in meta:
        original_id = meta["id"]
        meta["id"] = ensure_string_id(original_id)
        platform = meta.get("platform", event_metadata.get("platform", "unknown"))
        # Log warnings for potential ID issues
        log_id_warnings(meta["id"], platform)
        # Validate ID format
        is_valid, error_msg = validate_post_id(meta["id"], platform)
        if not is_valid:
            logger.warning(f"Invalid post ID format: {error_msg}")

    # Add batch context
    meta["job_id"] = event_metadata.get("job_id")
    meta["batch_index"] = event_metadata.get("batch_index")
    meta["task_type"] = event_metadata.get("task_type")
    meta["keyword_source"] = event_metadata.get("keyword")

    # Add pipeline version
    platform = meta.get("platform", event_metadata.get("platform", "unknown"))
    meta["pipeline_version"] = f"crawler_{platform.lower()}_v3"

    # Add project_id
    if project_id:
        meta["project_id"] = project_id

    # Parse crawled_at timestamp
    timestamp = event_metadata.get("timestamp")
    if timestamp:
        try:
            meta["crawled_at"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            meta["crawled_at"] = datetime.utcnow()

    enriched["meta"] = meta
    return enriched


def save_error_record(
    item: dict[str, Any],
    event_metadata: dict[str, Any],
    project_id: Optional[str],
    error_repo: CrawlErrorRepository,
) -> ItemProcessingResult:
    """Save an error record to the database.

    Args:
        item: Error item data
        event_metadata: Event metadata
        project_id: Extracted project ID
        error_repo: Error repository instance

    Returns:
        ItemProcessingResult with error status
    """
    meta = item.get("meta") or {}
    # Ensure content_id is string to prevent BigInt precision loss
    content_id = ensure_string_id(meta.get("id")) or "unknown"
    platform = meta.get("platform", event_metadata.get("platform", "unknown"))

    error_info = extract_error_info(item)

    error_data = {
        "content_id": content_id,
        "project_id": project_id,
        "job_id": event_metadata.get("job_id", ""),
        "platform": platform,
        "error_code": error_info["error_code"],
        "error_message": error_info["error_message"],
        "error_details": error_info["error_details"],
        "permalink": meta.get("permalink"),
    }

    try:
        error_repo.save(error_data)
        logger.debug(
            f"Saved error record: content_id={content_id}, error_code={error_info['error_code']}"
        )
    except Exception as exc:
        logger.error(f"Failed to save error record for {content_id}: {exc}")

    return ItemProcessingResult(
        content_id=content_id,
        status="error",
        error_code=error_info["error_code"],
        error_message=error_info["error_message"],
    )


def log_batch_completion(
    event_id: str,
    job_id: str,
    stats: BatchProcessingStats,
) -> None:
    """Log batch completion with statistics.

    Args:
        event_id: Event identifier
        job_id: Job identifier
        stats: Batch processing statistics
    """
    logger.info(
        f"Batch completed: event_id={event_id}, job_id={job_id}, "
        f"success={stats.success_count}, errors={stats.error_count}, success_rate={stats.success_rate:.1f}%"
    )

    if stats.error_distribution:
        logger.info(f"Error distribution for job_id={job_id}: {stats.error_distribution}")

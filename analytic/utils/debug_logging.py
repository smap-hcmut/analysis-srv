"""Debug logging utilities for production data monitoring.

This module provides utilities for detailed logging of data extraction
from crawler events, controlled by environment variables.

Environment Variables:
    DEBUG_RAW_DATA: Set to "true" for full debug logging,
                   "sample" for 1-in-100 sampling, "false" to disable.
    DEBUG_SAMPLE_RATE: Sample rate when DEBUG_RAW_DATA="sample" (default: 100)
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from core.logger import logger
from core.config import settings


# Counter for sampling
_sample_counter = 0


def should_log_debug() -> bool:
    """Check if debug logging should be performed.

    Returns:
        True if debug logging is enabled or sampling hits.
    """
    global _sample_counter

    debug_mode = settings.debug_raw_data.lower()

    if debug_mode == "true":
        return True

    if debug_mode == "sample":
        _sample_counter += 1
        if _sample_counter >= settings.debug_sample_rate:
            _sample_counter = 0
            return True

    return False


def log_raw_event_payload(envelope: Dict[str, Any], event_id: str = "unknown") -> None:
    """Log raw event payload structure for debugging.

    Only logs when DEBUG_RAW_DATA is enabled.

    Args:
        envelope: Raw event envelope from RabbitMQ
        event_id: Event identifier for correlation
    """
    if not should_log_debug():
        return

    # Sanitize PII - remove actual content, keep structure
    sanitized = _sanitize_for_logging(envelope)

    logger.debug(f"RAW EVENT PAYLOAD (event_id={event_id}): {sanitized}")


def log_extracted_item_data(
    item: Dict[str, Any],
    content_id: str = "unknown",
    platform: str = "unknown",
) -> None:
    """Log extracted item data for debugging.

    Args:
        item: Item data from batch
        content_id: Content identifier
        platform: Platform name
    """
    if not should_log_debug():
        return

    meta = item.get("meta", {})

    meta_keys = list(meta.keys())
    content_keys = list(item.get("content", {}).keys())
    interaction_keys = list(item.get("interaction", {}).keys())
    logger.debug(
        f"EXTRACTED ITEM DATA: content_id={content_id}, platform={platform}, "
        f"meta_keys={meta_keys}, content_keys={content_keys}, interaction_keys={interaction_keys}"
    )


def log_analytics_payload_before_save(
    payload: Dict[str, Any],
    content_id: str = "unknown",
) -> None:
    """Log final analytics payload before database save.

    Args:
        payload: Analytics payload to be saved
        content_id: Content identifier
    """
    if not should_log_debug():
        return

    # Log key fields for debugging
    job_id = payload.get("job_id")
    batch_index = payload.get("batch_index")
    task_type = payload.get("task_type")
    keyword_source = payload.get("keyword_source")
    crawled_at = payload.get("crawled_at")
    pipeline_version = payload.get("pipeline_version")
    is_viral = payload.get("is_viral")
    is_viral_type = type(is_viral).__name__
    is_kol = payload.get("is_kol")
    is_kol_type = type(is_kol).__name__
    logger.debug(
        f"ANALYTICS PAYLOAD BEFORE SAVE: content_id={content_id}, "
        f"job_id={job_id}, batch_index={batch_index}, task_type={task_type}, keyword_source={keyword_source}, "
        f"crawled_at={crawled_at}, pipeline_version={pipeline_version}, "
        f"is_viral={is_viral} (type={is_viral_type}), is_kol={is_kol} (type={is_kol_type})"
    )


def log_metadata_extraction_paths(
    field_name: str,
    value: Any,
    source_path: str,
    event_id: str = "unknown",
) -> None:
    """Log which field path was used for metadata extraction.

    Args:
        field_name: Name of the field being extracted
        value: Extracted value
        source_path: Path where value was found (e.g., "payload.job_id")
        event_id: Event identifier
    """
    if not should_log_debug():
        return

    value_type = type(value).__name__ if value is not None else "None"
    logger.debug(
        f"METADATA EXTRACTION: field={field_name}, value={value}, source={source_path}, "
        f"type={value_type} (event_id={event_id})"
    )


def log_missing_metadata_fields(
    missing_fields: List[str],
    searched_paths: Dict[str, List[str]],
    event_id: str = "unknown",
) -> None:
    """Log warning for missing metadata fields.

    Args:
        missing_fields: List of field names that were not found
        searched_paths: Dict mapping field names to paths that were searched
        event_id: Event identifier
    """
    if not missing_fields:
        return

    logger.warning(
        f"MISSING METADATA FIELDS: fields={missing_fields}, searched_paths={searched_paths} (event_id={event_id})"
    )


def log_data_quality_metrics(
    total_items: int,
    items_with_full_metadata: int,
    items_with_sentiment: int,
    truncated_ids: int,
    job_id: str = "unknown",
) -> None:
    """Log data quality metrics after batch processing.

    Args:
        total_items: Total items in batch
        items_with_full_metadata: Items with complete metadata
        items_with_sentiment: Items with actual sentiment (not neutral default)
        truncated_ids: Items with potentially truncated IDs
        job_id: Job identifier
    """
    if total_items == 0:
        return

    metadata_pct = (items_with_full_metadata / total_items) * 100
    sentiment_pct = (items_with_sentiment / total_items) * 100

    logger.info(
        f"DATA QUALITY METRICS: job_id={job_id}, total={total_items}, "
        f"metadata_complete={metadata_pct:.1f}%, sentiment_analyzed={sentiment_pct:.1f}%, truncated_ids={truncated_ids}"
    )

    # Alert on low metadata completeness
    if metadata_pct < 80:
        logger.warning(
            f"LOW METADATA COMPLETENESS: job_id={job_id}, only {metadata_pct:.1f}% of items have full metadata"
        )


def _sanitize_for_logging(data: Any, max_depth: int = 3, current_depth: int = 0) -> Any:
    """Sanitize data for logging by removing PII and truncating large values.

    Args:
        data: Data to sanitize
        max_depth: Maximum recursion depth
        current_depth: Current recursion depth

    Returns:
        Sanitized data safe for logging
    """
    if current_depth >= max_depth:
        return "<truncated>"

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Skip content fields that may contain PII
            if key in ("text", "description", "transcription", "comments", "author"):
                sanitized[key] = f"<{type(value).__name__}>"
            else:
                sanitized[key] = _sanitize_for_logging(value, max_depth, current_depth + 1)
        return sanitized

    if isinstance(data, list):
        if len(data) > 3:
            return [
                _sanitize_for_logging(data[0], max_depth, current_depth + 1),
                f"<... {len(data) - 2} more items ...>",
                _sanitize_for_logging(data[-1], max_depth, current_depth + 1),
            ]
        return [_sanitize_for_logging(item, max_depth, current_depth + 1) for item in data]

    if isinstance(data, str) and len(data) > 100:
        return data[:50] + "..." + data[-20:]

    return data

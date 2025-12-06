"""Unit tests for item processor module."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from internal.consumers.item_processor import (
    ItemProcessingResult,
    BatchProcessingStats,
    is_error_item,
    extract_error_info,
    enrich_item_with_context,
)
from core.constants import ErrorCategory


class TestItemProcessingResult:
    """Tests for ItemProcessingResult class."""

    def test_success_result(self):
        """Create success result."""
        result = ItemProcessingResult(
            content_id="post_123",
            status="success",
            impact_score=75.5,
        )

        assert result.content_id == "post_123"
        assert result.status == "success"
        assert result.impact_score == 75.5
        assert result.error_code is None

    def test_error_result(self):
        """Create error result."""
        result = ItemProcessingResult(
            content_id="post_456",
            status="error",
            error_code="RATE_LIMITED",
            error_message="Too many requests",
        )

        assert result.content_id == "post_456"
        assert result.status == "error"
        assert result.error_code == "RATE_LIMITED"
        assert result.error_message == "Too many requests"

    def test_to_dict(self):
        """Convert result to dictionary."""
        result = ItemProcessingResult(
            content_id="post_789",
            status="success",
            impact_score=50.0,
        )

        d = result.to_dict()

        assert d["content_id"] == "post_789"
        assert d["status"] == "success"
        assert d["impact_score"] == 50.0


class TestBatchProcessingStats:
    """Tests for BatchProcessingStats class."""

    def test_initial_state(self):
        """Initial stats should be zero."""
        stats = BatchProcessingStats()

        assert stats.success_count == 0
        assert stats.error_count == 0
        assert stats.total_count == 0
        assert stats.success_rate == 0.0

    def test_add_success(self):
        """Add success result."""
        stats = BatchProcessingStats()
        result = ItemProcessingResult("post_1", "success", impact_score=50.0)

        stats.add_success(result)

        assert stats.success_count == 1
        assert stats.error_count == 0
        assert stats.total_count == 1
        assert stats.success_rate == 100.0

    def test_add_error(self):
        """Add error result."""
        stats = BatchProcessingStats()
        result = ItemProcessingResult("post_1", "error", error_code="RATE_LIMITED")

        stats.add_error(result)

        assert stats.success_count == 0
        assert stats.error_count == 1
        assert stats.error_distribution == {"RATE_LIMITED": 1}

    def test_mixed_results(self):
        """Add mixed success and error results."""
        stats = BatchProcessingStats()

        stats.add_success(ItemProcessingResult("post_1", "success"))
        stats.add_success(ItemProcessingResult("post_2", "success"))
        stats.add_error(ItemProcessingResult("post_3", "error", error_code="RATE_LIMITED"))
        stats.add_error(ItemProcessingResult("post_4", "error", error_code="RATE_LIMITED"))
        stats.add_error(ItemProcessingResult("post_5", "error", error_code="CONTENT_REMOVED"))

        assert stats.success_count == 2
        assert stats.error_count == 3
        assert stats.total_count == 5
        assert stats.success_rate == 40.0
        assert stats.error_distribution == {"RATE_LIMITED": 2, "CONTENT_REMOVED": 1}

    def test_to_dict(self):
        """Convert stats to dictionary."""
        stats = BatchProcessingStats()
        stats.add_success(ItemProcessingResult("post_1", "success"))
        stats.add_error(ItemProcessingResult("post_2", "error", error_code="TIMEOUT"))

        d = stats.to_dict()

        assert d["success_count"] == 1
        assert d["error_count"] == 1
        assert d["total_count"] == 2
        assert d["success_rate"] == 50.0
        assert d["error_distribution"] == {"TIMEOUT": 1}


class TestIsErrorItem:
    """Tests for is_error_item function."""

    def test_error_item(self):
        """Item with fetch_status=error should return True."""
        item = {"meta": {"id": "post_1", "fetch_status": "error"}}
        assert is_error_item(item) is True

    def test_success_item(self):
        """Item with fetch_status=success should return False."""
        item = {"meta": {"id": "post_1", "fetch_status": "success"}}
        assert is_error_item(item) is False

    def test_no_fetch_status(self):
        """Item without fetch_status should return False."""
        item = {"meta": {"id": "post_1"}}
        assert is_error_item(item) is False

    def test_no_meta(self):
        """Item without meta should return False."""
        item = {"content": "Hello"}
        assert is_error_item(item) is False


class TestExtractErrorInfo:
    """Tests for extract_error_info function."""

    def test_full_error_info(self):
        """Extract full error information."""
        item = {
            "meta": {
                "id": "post_1",
                "fetch_status": "error",
                "error_code": "RATE_LIMITED",
                "error_message": "Too many requests",
                "error_details": {"retry_after": 60},
            }
        }

        info = extract_error_info(item)

        assert info["error_code"] == "RATE_LIMITED"
        assert info["error_category"] == "rate_limiting"
        assert info["error_message"] == "Too many requests"
        assert info["error_details"] == {"retry_after": 60}

    def test_minimal_error_info(self):
        """Extract error info with minimal data."""
        item = {"meta": {"id": "post_1", "fetch_status": "error"}}

        info = extract_error_info(item)

        assert info["error_code"] == "UNKNOWN_ERROR"
        assert info["error_category"] == "generic"
        assert info["error_message"] == ""
        assert info["error_details"] == {}

    def test_error_categorization(self):
        """Error codes should be categorized correctly."""
        test_cases = [
            ("RATE_LIMITED", "rate_limiting"),
            ("CONTENT_REMOVED", "content"),
            ("NETWORK_ERROR", "network"),
            ("PARSE_ERROR", "parsing"),
            ("MEDIA_TOO_LARGE", "media"),
            ("STORAGE_ERROR", "storage"),
            ("UNKNOWN_ERROR", "generic"),
        ]

        for error_code, expected_category in test_cases:
            item = {"meta": {"error_code": error_code}}
            info = extract_error_info(item)
            assert info["error_category"] == expected_category, f"Failed for {error_code}"


class TestEnrichItemWithContext:
    """Tests for enrich_item_with_context function."""

    def test_enrich_with_full_context(self):
        """Enrich item with full event metadata."""
        item = {
            "meta": {"id": "post_1", "platform": "tiktok"},
            "content": "Hello world",
        }
        event_metadata = {
            "job_id": "proj_abc-brand-0",
            "batch_index": 1,
            "task_type": "research_and_crawl",
            "keyword": "VinFast VF8",
            "timestamp": "2025-12-06T10:15:30Z",
        }
        project_id = "proj_abc"

        enriched = enrich_item_with_context(item, event_metadata, project_id)

        assert enriched["meta"]["job_id"] == "proj_abc-brand-0"
        assert enriched["meta"]["batch_index"] == 1
        assert enriched["meta"]["task_type"] == "research_and_crawl"
        assert enriched["meta"]["keyword_source"] == "VinFast VF8"
        assert enriched["meta"]["project_id"] == "proj_abc"
        assert enriched["meta"]["pipeline_version"] == "crawler_tiktok_v3"
        assert enriched["content"] == "Hello world"  # Original content preserved

    def test_enrich_without_project_id(self):
        """Enrich item without project_id (dry-run)."""
        item = {"meta": {"id": "post_1", "platform": "youtube"}}
        event_metadata = {"job_id": "550e8400-e29b-41d4-a716-446655440000"}

        enriched = enrich_item_with_context(item, event_metadata, None)

        assert "project_id" not in enriched["meta"]
        assert enriched["meta"]["pipeline_version"] == "crawler_youtube_v3"

    def test_original_item_not_modified(self):
        """Original item should not be modified."""
        item = {"meta": {"id": "post_1"}}
        event_metadata = {"job_id": "proj_abc-brand-0"}

        enriched = enrich_item_with_context(item, event_metadata, "proj_abc")

        assert "job_id" not in item["meta"]
        assert enriched["meta"]["job_id"] == "proj_abc-brand-0"

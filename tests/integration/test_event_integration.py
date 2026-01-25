"""Integration tests for event schema parsing and batch processing.

These tests validate the complete flow from event parsing to item processing.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from internal.consumers.main import (
    parse_minio_path,
    validate_event_format,
    parse_event_metadata,
    enrich_with_batch_context,
    process_single_item,
)
from internal.consumers.item_processor import (
    is_error_item,
    extract_error_info,
    BatchProcessingStats,
    ItemProcessingResult,
)
from utils.project_id_extractor import extract_project_id
from core.constants import categorize_error, ErrorCategory


class TestEventSchemaParsingIntegration:
    """Integration tests for event schema parsing (Task 7.1)."""

    def test_full_event_parsing_flow(self):
        """Test complete event parsing from raw envelope to metadata."""
        # Simulate raw event from RabbitMQ
        raw_event = {
            "event_id": "evt_abc123",
            "event_type": "data.collected",
            "timestamp": "2025-12-06T10:15:30Z",
            "payload": {
                "minio_path": "crawl-results/tiktok/2025/12/06/batch_001.json",
                "project_id": "proj_xyz",
                "job_id": "proj_xyz-brand-0",
                "batch_index": 1,
                "content_count": 50,
                "platform": "tiktok",
                "task_type": "research_and_crawl",
                "keyword": "VinFast VF8",
            },
        }

        # Step 1: Validate event format
        assert validate_event_format(raw_event) is True

        # Step 2: Parse metadata
        metadata = parse_event_metadata(raw_event)
        assert metadata["event_id"] == "evt_abc123"
        assert metadata["job_id"] == "proj_xyz-brand-0"
        assert metadata["platform"] == "tiktok"
        assert metadata["content_count"] == 50

        # Step 3: Parse MinIO path
        bucket, path = parse_minio_path(metadata["minio_path"])
        assert bucket == "crawl-results"
        assert path == "tiktok/2025/12/06/batch_001.json"

        # Step 4: Extract project_id from job_id
        project_id = extract_project_id(metadata["job_id"])
        assert project_id == "proj_xyz"

    def test_invalid_event_format_detection(self):
        """Test invalid event format is correctly detected."""
        invalid_event = {
            "data_ref": {
                "bucket": "analytics",
                "path": "posts/post_123.json",
            }
        }

        # Event without payload.minio_path is invalid
        assert validate_event_format(invalid_event) is False

    def test_valid_event_format_detection(self):
        """Test valid event format is correctly detected."""
        valid_event = {
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
            }
        }

        assert validate_event_format(valid_event) is True


class TestBatchProcessingIntegration:
    """Integration tests for batch processing (Task 7.2)."""

    def test_batch_with_mixed_success_and_error(self):
        """Test batch processing with 1 success and 1 error item."""
        # Create batch items
        success_item = {
            "meta": {
                "id": "post_001",
                "platform": "tiktok",
                "fetch_status": "success",
            },
            "content": {"text": "Great product!"},
            "interactions": {"likes": 100, "comments_count": 10},
        }

        error_item = {
            "meta": {
                "id": "post_002",
                "platform": "tiktok",
                "fetch_status": "error",
                "error_code": "RATE_LIMITED",
                "error_message": "Too many requests",
            },
        }

        batch_items = [success_item, error_item]

        # Process batch
        stats = BatchProcessingStats()

        for item in batch_items:
            if is_error_item(item):
                error_info = extract_error_info(item)
                result = ItemProcessingResult(
                    content_id=item["meta"]["id"],
                    status="error",
                    error_code=error_info["error_code"],
                )
                stats.add_error(result)
            else:
                result = ItemProcessingResult(
                    content_id=item["meta"]["id"],
                    status="success",
                    impact_score=50.0,
                )
                stats.add_success(result)

        # Verify stats
        assert stats.success_count == 1
        assert stats.error_count == 1
        assert stats.total_count == 2
        assert stats.success_rate == 50.0
        assert stats.error_distribution == {"RATE_LIMITED": 1}


class TestProjectIdExtractionIntegration:
    """Integration tests for project_id extraction (Task 7.3)."""

    def test_all_job_id_formats(self):
        """Test project_id extraction for all supported formats."""
        test_cases = [
            # (job_id, expected_project_id)
            ("proj_abc-brand-0", "proj_abc"),
            ("proj_xyz-toyota-5", "proj_xyz"),
            ("my-project-name-competitor-10", "my-project-name"),
            ("proj-2024-q1-campaign-brand-3", "proj-2024-q1-campaign"),
            ("550e8400-e29b-41d4-a716-446655440000", None),  # UUID dry-run
            ("", None),
            ("invalid", None),
            ("proj-0", None),  # Too few parts
        ]

        for job_id, expected in test_cases:
            result = extract_project_id(job_id)
            assert result == expected, f"Failed for job_id={job_id}"


class TestErrorCategorizationIntegration:
    """Integration tests for error categorization (Task 7.4)."""

    def test_all_error_categories(self):
        """Test error categorization for all error codes."""
        test_cases = [
            # Rate limiting
            ("RATE_LIMITED", ErrorCategory.RATE_LIMITING),
            ("AUTH_FAILED", ErrorCategory.RATE_LIMITING),
            ("ACCESS_DENIED", ErrorCategory.RATE_LIMITING),
            # Content
            ("CONTENT_REMOVED", ErrorCategory.CONTENT),
            ("CONTENT_NOT_FOUND", ErrorCategory.CONTENT),
            ("CONTENT_UNAVAILABLE", ErrorCategory.CONTENT),
            # Network
            ("NETWORK_ERROR", ErrorCategory.NETWORK),
            ("TIMEOUT", ErrorCategory.NETWORK),
            ("CONNECTION_REFUSED", ErrorCategory.NETWORK),
            ("DNS_ERROR", ErrorCategory.NETWORK),
            # Parsing
            ("PARSE_ERROR", ErrorCategory.PARSING),
            ("INVALID_URL", ErrorCategory.PARSING),
            ("INVALID_RESPONSE", ErrorCategory.PARSING),
            # Media
            ("MEDIA_DOWNLOAD_FAILED", ErrorCategory.MEDIA),
            ("MEDIA_TOO_LARGE", ErrorCategory.MEDIA),
            ("MEDIA_FORMAT_ERROR", ErrorCategory.MEDIA),
            # Storage
            ("STORAGE_ERROR", ErrorCategory.STORAGE),
            ("UPLOAD_FAILED", ErrorCategory.STORAGE),
            ("DATABASE_ERROR", ErrorCategory.STORAGE),
            # Generic
            ("UNKNOWN_ERROR", ErrorCategory.GENERIC),
            ("INTERNAL_ERROR", ErrorCategory.GENERIC),
            ("SOME_UNKNOWN_CODE", ErrorCategory.GENERIC),
        ]

        for error_code, expected_category in test_cases:
            result = categorize_error(error_code)
            assert result == expected_category, f"Failed for error_code={error_code}"


class TestEventFormatValidation:
    """Integration tests for event format validation."""

    def test_valid_event_with_all_fields(self):
        """Test valid event format with complete payload."""
        event = {
            "event_id": "evt_123",
            "event_type": "data.collected",
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
                "job_id": "proj_abc-brand-0",
            },
        }
        assert validate_event_format(event) is True

    def test_valid_event_minimal(self):
        """Test valid event format with minimal payload."""
        event = {
            "payload": {
                "minio_path": "bucket/path.json",
            },
        }
        assert validate_event_format(event) is True

    def test_invalid_event_no_payload(self):
        """Test invalid event without payload."""
        event = {
            "event_id": "evt_123",
        }
        assert validate_event_format(event) is False

    def test_invalid_event_no_minio_path(self):
        """Test invalid event without minio_path."""
        event = {
            "payload": {
                "job_id": "proj_abc-brand-0",
            },
        }
        assert validate_event_format(event) is False


class TestItemEnrichmentIntegration:
    """Integration tests for item enrichment with batch context."""

    def test_enrich_success_item(self):
        """Test enriching success item with full context."""
        item = {
            "meta": {
                "id": "post_123",
                "platform": "tiktok",
                "fetch_status": "success",
            },
            "content": {"text": "Hello world"},
        }

        event_metadata = {
            "job_id": "proj_abc-brand-0",
            "batch_index": 1,
            "task_type": "research_and_crawl",
            "keyword": "VinFast VF8",
            "timestamp": "2025-12-06T10:15:30Z",
        }

        enriched = enrich_with_batch_context(item, event_metadata, "proj_abc")

        assert enriched["meta"]["job_id"] == "proj_abc-brand-0"
        assert enriched["meta"]["batch_index"] == 1
        assert enriched["meta"]["task_type"] == "research_and_crawl"
        assert enriched["meta"]["keyword_source"] == "VinFast VF8"
        assert enriched["meta"]["project_id"] == "proj_abc"
        assert enriched["meta"]["pipeline_version"] == "crawler_tiktok_v3"
        assert "crawled_at" in enriched["meta"]

    def test_enrich_dry_run_item(self):
        """Test enriching item without project_id (dry-run)."""
        item = {
            "meta": {
                "id": "post_456",
                "platform": "youtube",
            },
        }

        event_metadata = {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "batch_index": 0,
        }

        enriched = enrich_with_batch_context(item, event_metadata, None)

        assert "project_id" not in enriched["meta"]
        assert enriched["meta"]["pipeline_version"] == "crawler_youtube_v3"

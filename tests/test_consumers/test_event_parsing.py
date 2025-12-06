"""Unit tests for event parsing and message format validation."""

import pytest

from internal.consumers.main import (
    parse_minio_path,
    validate_event_format,
    parse_event_metadata,
)


class TestParseMinioPath:
    """Tests for parse_minio_path function."""

    def test_valid_path(self):
        """Parse valid MinIO path."""
        bucket, path = parse_minio_path("crawl-results/tiktok/2025/12/06/batch.json")
        assert bucket == "crawl-results"
        assert path == "tiktok/2025/12/06/batch.json"

    def test_simple_path(self):
        """Parse simple two-part path."""
        bucket, path = parse_minio_path("bucket/file.json")
        assert bucket == "bucket"
        assert path == "file.json"

    def test_empty_path_raises_error(self):
        """Empty path should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_minio_path("")

    def test_no_slash_raises_error(self):
        """Path without slash should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid minio_path format"):
            parse_minio_path("bucket")

    def test_trailing_slash_raises_error(self):
        """Path with only bucket and trailing slash should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid minio_path format"):
            parse_minio_path("bucket/")


class TestValidateEventFormat:
    """Tests for validate_event_format function."""

    def test_valid_event_format(self):
        """Validate event format with payload.minio_path."""
        envelope = {
            "event_id": "evt_123",
            "event_type": "data.collected",
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
                "job_id": "proj_abc-brand-0",
            },
        }
        assert validate_event_format(envelope) is True

    def test_invalid_event_no_payload(self):
        """Event without payload is invalid."""
        envelope = {
            "data_ref": {
                "bucket": "analytics",
                "path": "posts/123.json",
            }
        }
        assert validate_event_format(envelope) is False

    def test_invalid_event_no_minio_path(self):
        """Event without minio_path is invalid."""
        envelope = {
            "payload": {
                "job_id": "proj_abc-brand-0",
            }
        }
        assert validate_event_format(envelope) is False

    def test_valid_event_minimal(self):
        """Minimal valid event with only minio_path."""
        envelope = {
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
            }
        }
        assert validate_event_format(envelope) is True


class TestParseEventMetadata:
    """Tests for parse_event_metadata function."""

    def test_full_metadata(self):
        """Parse event with all metadata fields."""
        envelope = {
            "event_id": "evt_123",
            "event_type": "data.collected",
            "timestamp": "2025-12-06T10:15:30Z",
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
                "project_id": "proj_abc",
                "job_id": "proj_abc-brand-0",
                "batch_index": 1,
                "content_count": 50,
                "platform": "tiktok",
                "task_type": "research_and_crawl",
                "keyword": "VinFast VF8",
            },
        }

        metadata = parse_event_metadata(envelope)

        assert metadata["event_id"] == "evt_123"
        assert metadata["event_type"] == "data.collected"
        assert metadata["timestamp"] == "2025-12-06T10:15:30Z"
        assert metadata["minio_path"] == "crawl-results/tiktok/batch.json"
        assert metadata["project_id"] == "proj_abc"
        assert metadata["job_id"] == "proj_abc-brand-0"
        assert metadata["batch_index"] == 1
        assert metadata["content_count"] == 50
        assert metadata["platform"] == "tiktok"
        assert metadata["task_type"] == "research_and_crawl"
        assert metadata["keyword"] == "VinFast VF8"

    def test_partial_metadata(self):
        """Parse event with partial metadata."""
        envelope = {
            "event_id": "evt_456",
            "payload": {
                "minio_path": "crawl-results/youtube/batch.json",
            },
        }

        metadata = parse_event_metadata(envelope)

        assert metadata["event_id"] == "evt_456"
        assert metadata["minio_path"] == "crawl-results/youtube/batch.json"
        assert metadata["job_id"] is None
        assert metadata["platform"] is None

    def test_empty_envelope(self):
        """Parse empty envelope returns None values."""
        metadata = parse_event_metadata({})

        assert metadata["event_id"] is None
        assert metadata["minio_path"] is None

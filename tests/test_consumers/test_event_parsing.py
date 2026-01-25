"""Unit tests for event parsing and message format validation."""

import pytest

from internal.consumers.main import (
    parse_minio_path,
    validate_event_format,
    parse_event_metadata,
    enrich_with_batch_context,
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
                "brand_name": "VinFast",
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
        assert metadata["brand_name"] == "VinFast"

    def test_brand_name_extraction(self):
        """Parse event extracts brand_name from payload (Contract v2.0)."""
        envelope = {
            "event_id": "evt_brand_test",
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
                "brand_name": "Toyota",
                "keyword": "Toyota Camry",
            },
        }

        metadata = parse_event_metadata(envelope)

        assert metadata["brand_name"] == "Toyota"
        assert metadata["keyword"] == "Toyota Camry"

    def test_missing_brand_name(self):
        """Parse event with missing brand_name returns None."""
        envelope = {
            "event_id": "evt_no_brand",
            "payload": {
                "minio_path": "crawl-results/tiktok/batch.json",
                "keyword": "VinFast VF8",
            },
        }

        metadata = parse_event_metadata(envelope)

        assert metadata["brand_name"] is None
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


class TestEnrichWithBatchContext:
    """Tests for enrich_with_batch_context function (Contract v2.0)."""

    def test_enrich_with_brand_and_keyword(self):
        """Enrich item with brand_name and keyword from event metadata."""
        item = {
            "meta": {"id": "post_123", "platform": "tiktok"},
            "content": {"text": "Review VinFast VF8"},
            "author": {"id": "author_1", "name": "Tech Reviewer"},
        }
        event_metadata = {
            "job_id": "proj_abc-brand-0",
            "batch_index": 1,
            "brand_name": "VinFast",
            "keyword": "VinFast VF8",
        }

        enriched = enrich_with_batch_context(item, event_metadata, "proj_abc")

        assert enriched["meta"]["brand_name"] == "VinFast"
        assert enriched["meta"]["keyword"] == "VinFast VF8"

    def test_enrich_with_content_fields(self):
        """Enrich item extracts content fields (Contract v2.0)."""
        item = {
            "meta": {
                "id": "post_123",
                "platform": "tiktok",
                "permalink": "https://tiktok.com/video/123",
            },
            "content": {
                "text": "Review chi tiết VinFast VF8",
                "transcription": "Xin chào các bạn...",
                "duration": 180,
                "hashtags": ["vinfast", "vf8", "review"],
            },
        }
        event_metadata = {"job_id": "proj_abc-brand-0"}

        enriched = enrich_with_batch_context(item, event_metadata, "proj_abc")

        assert enriched["meta"]["content_text"] == "Review chi tiết VinFast VF8"
        assert enriched["meta"]["content_transcription"] == "Xin chào các bạn..."
        assert enriched["meta"]["media_duration"] == 180
        assert enriched["meta"]["hashtags"] == ["vinfast", "vf8", "review"]
        assert enriched["meta"]["permalink"] == "https://tiktok.com/video/123"

    def test_enrich_with_author_fields(self):
        """Enrich item extracts author fields (Contract v2.0)."""
        item = {
            "meta": {"id": "post_123", "platform": "tiktok"},
            "author": {
                "id": "author_456",
                "name": "Tech Reviewer",
                "username": "@techreviewer",
                "avatar_url": "https://cdn.tiktok.com/avatar/xxx",
                "is_verified": True,
                "followers": 50000,
            },
        }
        event_metadata = {"job_id": "proj_abc-brand-0"}

        enriched = enrich_with_batch_context(item, event_metadata, "proj_abc")

        assert enriched["meta"]["author_id"] == "author_456"
        assert enriched["meta"]["author_name"] == "Tech Reviewer"
        assert enriched["meta"]["author_username"] == "@techreviewer"
        assert enriched["meta"]["author_avatar_url"] == "https://cdn.tiktok.com/avatar/xxx"
        assert enriched["meta"]["author_is_verified"] is True

    def test_enrich_with_missing_optional_fields(self):
        """Enrich item handles missing optional fields gracefully."""
        item = {
            "meta": {"id": "post_123", "platform": "tiktok"},
            "content": {"text": "Simple post"},
            # No author, no transcription, no hashtags
        }
        event_metadata = {
            "job_id": "proj_abc-brand-0",
            # No brand_name, no keyword
        }

        enriched = enrich_with_batch_context(item, event_metadata, "proj_abc")

        # Should not raise, missing fields should be None
        assert enriched["meta"]["brand_name"] is None
        assert enriched["meta"]["keyword"] is None
        assert enriched["meta"]["content_transcription"] is None
        assert enriched["meta"]["hashtags"] is None
        assert enriched["meta"]["author_id"] is None
        assert enriched["meta"]["author_name"] is None

    def test_enrich_preserves_original_item(self):
        """Enrich should not modify original item."""
        item = {
            "meta": {"id": "post_123", "platform": "tiktok"},
            "content": {"text": "Original content"},
        }
        event_metadata = {"job_id": "proj_abc-brand-0", "brand_name": "VinFast"}

        enriched = enrich_with_batch_context(item, event_metadata, "proj_abc")

        # Original item should not have brand_name
        assert "brand_name" not in item["meta"]
        # Enriched item should have brand_name
        assert enriched["meta"]["brand_name"] == "VinFast"

    def test_enrich_full_contract_v2_item(self):
        """Enrich complete Contract v2.0 item with all fields."""
        item = {
            "meta": {
                "id": "7441234567890123456",
                "platform": "TIKTOK",
                "fetch_status": "success",
                "published_at": "2025-12-10T08:00:00Z",
                "permalink": "https://tiktok.com/@techreviewer/video/7441234567890123456",
            },
            "content": {
                "text": "Review chi tiết VinFast VF8 sau 1 tháng sử dụng",
                "transcription": "Xin chào các bạn, hôm nay mình sẽ review...",
                "duration": 180,
                "hashtags": ["vinfast", "vf8", "review"],
            },
            "interaction": {
                "views": 10000,
                "likes": 500,
                "comments_count": 50,
                "shares": 100,
                "saves": 25,
            },
            "author": {
                "id": "author_456",
                "name": "Tech Reviewer",
                "username": "@techreviewer",
                "avatar_url": "https://p16-sign.tiktokcdn.com/avatar/xxx",
                "followers": 50000,
                "is_verified": True,
            },
            "comments": [
                {"id": "cmt_001", "text": "Video hay quá!", "author_name": "User123", "likes": 10},
            ],
        }
        event_metadata = {
            "event_id": "evt_123",
            "timestamp": "2025-12-17T10:00:00Z",
            "job_id": "proj_xyz-brand-0",
            "batch_index": 0,
            "task_type": "research_and_crawl",
            "brand_name": "VinFast",
            "keyword": "VinFast VF8",
        }

        enriched = enrich_with_batch_context(item, event_metadata, "proj_xyz")

        # Verify all Contract v2.0 fields are extracted
        meta = enriched["meta"]
        assert meta["brand_name"] == "VinFast"
        assert meta["keyword"] == "VinFast VF8"
        assert meta["content_text"] == "Review chi tiết VinFast VF8 sau 1 tháng sử dụng"
        assert meta["content_transcription"] == "Xin chào các bạn, hôm nay mình sẽ review..."
        assert meta["media_duration"] == 180
        assert meta["hashtags"] == ["vinfast", "vf8", "review"]
        assert meta["permalink"] == "https://tiktok.com/@techreviewer/video/7441234567890123456"
        assert meta["author_id"] == "author_456"
        assert meta["author_name"] == "Tech Reviewer"
        assert meta["author_username"] == "@techreviewer"
        assert meta["author_avatar_url"] == "https://p16-sign.tiktokcdn.com/avatar/xxx"
        assert meta["author_is_verified"] is True
        assert meta["job_id"] == "proj_xyz-brand-0"
        assert meta["project_id"] == "proj_xyz"

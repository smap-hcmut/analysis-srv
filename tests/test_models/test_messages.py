"""Unit tests for message types used in result publishing.

Tests the dataclasses and serialization for AnalyzeResultMessage
and related types.
"""

import json
import pytest

from models.messages import (
    AnalyzeError,
    AnalyzeItem,
    AnalyzeResultPayload,
    AnalyzeResultMessage,
    create_success_result,
    create_error_result,
)


class TestAnalyzeError:
    """Tests for AnalyzeError dataclass."""

    def test_create_error(self):
        """Test creating an AnalyzeError."""
        error = AnalyzeError(content_id="video_123", error="Failed to parse")
        assert error.content_id == "video_123"
        assert error.error == "Failed to parse"

    def test_to_dict(self):
        """Test converting AnalyzeError to dictionary."""
        error = AnalyzeError(content_id="video_123", error="Failed to parse")
        result = error.to_dict()
        assert result == {"content_id": "video_123", "error": "Failed to parse"}


class TestAnalyzeItem:
    """Tests for AnalyzeItem dataclass."""

    def test_create_item_minimal(self):
        """Test creating an AnalyzeItem with minimal fields."""
        item = AnalyzeItem(content_id="video_123")
        assert item.content_id == "video_123"
        assert item.sentiment is None
        assert item.sentiment_score is None
        assert item.impact_score is None

    def test_create_item_full(self):
        """Test creating an AnalyzeItem with all fields."""
        item = AnalyzeItem(
            content_id="video_123",
            sentiment="POSITIVE",
            sentiment_score=0.85,
            impact_score=75.0,
        )
        assert item.content_id == "video_123"
        assert item.sentiment == "POSITIVE"
        assert item.sentiment_score == 0.85
        assert item.impact_score == 75.0

    def test_to_dict_minimal(self):
        """Test to_dict excludes None values."""
        item = AnalyzeItem(content_id="video_123")
        result = item.to_dict()
        assert result == {"content_id": "video_123"}
        assert "sentiment" not in result
        assert "sentiment_score" not in result
        assert "impact_score" not in result

    def test_to_dict_full(self):
        """Test to_dict includes all non-None values."""
        item = AnalyzeItem(
            content_id="video_123",
            sentiment="POSITIVE",
            sentiment_score=0.85,
            impact_score=75.0,
        )
        result = item.to_dict()
        assert result == {
            "content_id": "video_123",
            "sentiment": "POSITIVE",
            "sentiment_score": 0.85,
            "impact_score": 75.0,
        }


class TestAnalyzeResultPayload:
    """Tests for AnalyzeResultPayload dataclass."""

    def test_create_payload_minimal(self):
        """Test creating payload with minimal fields."""
        payload = AnalyzeResultPayload(project_id="proj_123", job_id="proj_123-brand-0")
        assert payload.project_id == "proj_123"
        assert payload.job_id == "proj_123-brand-0"
        assert payload.task_type == "analyze_result"
        assert payload.batch_size == 0
        assert payload.success_count == 0
        assert payload.error_count == 0
        assert payload.results == []
        assert payload.errors == []

    def test_create_payload_full(self):
        """Test creating payload with all fields."""
        results = [AnalyzeItem(content_id="v1", sentiment="POSITIVE")]
        errors = [AnalyzeError(content_id="v2", error="Failed")]

        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            task_type="analyze_result",
            batch_size=50,
            success_count=48,
            error_count=2,
            results=results,
            errors=errors,
        )

        assert payload.batch_size == 50
        assert payload.success_count == 48
        assert payload.error_count == 2
        assert len(payload.results) == 1
        assert len(payload.errors) == 1

    def test_to_dict(self):
        """Test converting payload to dictionary."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
            results=[AnalyzeItem(content_id="v1")],
            errors=[AnalyzeError(content_id="v2", error="Failed")],
        )

        result = payload.to_dict()

        assert result["project_id"] == "proj_123"
        assert result["job_id"] == "proj_123-brand-0"
        assert result["task_type"] == "analyze_result"
        assert result["batch_size"] == 50
        assert result["success_count"] == 48
        assert result["error_count"] == 2
        assert result["results"] == [{"content_id": "v1"}]
        assert result["errors"] == [{"content_id": "v2", "error": "Failed"}]


class TestAnalyzeResultMessage:
    """Tests for AnalyzeResultMessage dataclass."""

    def test_create_success_message(self):
        """Test creating a success message."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )
        msg = AnalyzeResultMessage(success=True, payload=payload)

        assert msg.success is True
        assert msg.payload.project_id == "proj_123"

    def test_create_failure_message(self):
        """Test creating a failure message."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=0,
            error_count=50,
        )
        msg = AnalyzeResultMessage(success=False, payload=payload)

        assert msg.success is False

    def test_to_dict(self):
        """Test converting message to dictionary."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )
        msg = AnalyzeResultMessage(success=True, payload=payload)

        result = msg.to_dict()

        assert result["success"] is True
        assert result["payload"]["project_id"] == "proj_123"
        assert result["payload"]["task_type"] == "analyze_result"

    def test_to_json(self):
        """Test JSON serialization."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )
        msg = AnalyzeResultMessage(success=True, payload=payload)

        json_str = msg.to_json()
        parsed = json.loads(json_str)

        assert parsed["success"] is True
        assert parsed["payload"]["project_id"] == "proj_123"

    def test_to_bytes(self):
        """Test bytes serialization for RabbitMQ."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
        )
        msg = AnalyzeResultMessage(success=True, payload=payload)

        data = msg.to_bytes()

        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["success"] is True

    def test_from_dict(self):
        """Test creating message from dictionary."""
        data = {
            "success": True,
            "payload": {
                "project_id": "proj_123",
                "job_id": "proj_123-brand-0",
                "task_type": "analyze_result",
                "batch_size": 50,
                "success_count": 48,
                "error_count": 2,
                "results": [{"content_id": "v1", "sentiment": "POSITIVE"}],
                "errors": [{"content_id": "v2", "error": "Failed"}],
            },
        }

        msg = AnalyzeResultMessage.from_dict(data)

        assert msg.success is True
        assert msg.payload.project_id == "proj_123"
        assert msg.payload.batch_size == 50
        assert len(msg.payload.results) == 1
        assert msg.payload.results[0].content_id == "v1"
        assert msg.payload.results[0].sentiment == "POSITIVE"
        assert len(msg.payload.errors) == 1
        assert msg.payload.errors[0].content_id == "v2"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_success_result(self):
        """Test create_success_result factory."""
        msg = create_success_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
            results=[AnalyzeItem(content_id="v1")],
            errors=[AnalyzeError(content_id="v2", error="Failed")],
        )

        assert msg.success is True  # error_count < batch_size
        assert msg.payload.task_type == "analyze_result"
        assert msg.payload.batch_size == 50
        assert msg.payload.success_count == 48
        assert msg.payload.error_count == 2

    def test_create_success_result_all_failed(self):
        """Test create_success_result when all items failed."""
        msg = create_success_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=0,
            error_count=50,
        )

        assert msg.success is False  # error_count >= batch_size

    def test_create_error_result(self):
        """Test create_error_result factory for batch-level errors."""
        msg = create_error_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            error_message="MinIO fetch failed: connection timeout",
        )

        assert msg.success is False
        assert msg.payload.task_type == "analyze_result"
        assert msg.payload.batch_size == 50
        assert msg.payload.success_count == 0
        assert msg.payload.error_count == 50
        assert msg.payload.results == []
        assert len(msg.payload.errors) == 1
        assert msg.payload.errors[0].content_id == "batch"
        assert "MinIO fetch failed" in msg.payload.errors[0].error

    def test_create_error_result_none_project_id(self):
        """Test create_error_result with None project_id (dry-run)."""
        msg = create_error_result(
            project_id=None,
            job_id="550e8400-e29b-41d4-a716-446655440000",
            batch_size=20,
            error_message="Test error",
        )

        assert msg.payload.project_id is None
        assert msg.payload.job_id == "550e8400-e29b-41d4-a716-446655440000"

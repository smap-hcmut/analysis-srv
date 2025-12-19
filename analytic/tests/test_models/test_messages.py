"""Unit tests for message types used in result publishing.

Tests the dataclasses and serialization for AnalyzeResultPayload
and related types following Collector contract spec.
"""

import json
import warnings
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
    """Tests for AnalyzeResultPayload dataclass (flat format for Collector)."""

    def test_create_payload_minimal(self):
        """Test creating payload with minimal fields."""
        payload = AnalyzeResultPayload(project_id="proj_123", job_id="proj_123-brand-0")
        assert payload.project_id == "proj_123"
        assert payload.job_id == "proj_123-brand-0"
        assert payload.task_type == "analyze_result"
        assert payload.batch_size == 0
        assert payload.success_count == 0
        assert payload.error_count == 0
        assert payload._results == []
        assert payload._errors == []

    def test_create_payload_full(self):
        """Test creating payload with all fields including internal."""
        results = [AnalyzeItem(content_id="v1", sentiment="POSITIVE")]
        errors = [AnalyzeError(content_id="v2", error="Failed")]

        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            task_type="analyze_result",
            batch_size=50,
            success_count=48,
            error_count=2,
            _results=results,
            _errors=errors,
        )

        assert payload.batch_size == 50
        assert payload.success_count == 48
        assert payload.error_count == 2
        assert len(payload._results) == 1
        assert len(payload._errors) == 1

    def test_to_dict_flat_format(self):
        """Test to_dict returns flat format with only 6 fields for Collector."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
            _results=[AnalyzeItem(content_id="v1")],
            _errors=[AnalyzeError(content_id="v2", error="Failed")],
        )

        result = payload.to_dict()

        # Verify flat structure with exactly 6 fields
        assert result == {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 48,
            "error_count": 2,
        }
        # Internal fields should NOT be in output
        assert "results" not in result
        assert "errors" not in result
        assert "_results" not in result
        assert "_errors" not in result

    def test_to_json(self):
        """Test JSON serialization produces flat format."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )

        json_str = payload.to_json()
        parsed = json.loads(json_str)

        assert parsed == {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 48,
            "error_count": 2,
        }

    def test_to_bytes(self):
        """Test bytes serialization for RabbitMQ."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
        )

        data = payload.to_bytes()

        assert isinstance(data, bytes)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["project_id"] == "proj_123"
        assert "success" not in parsed  # No wrapper

    def test_from_dict_flat_format(self):
        """Test creating payload from flat dictionary."""
        data = {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 48,
            "error_count": 2,
        }

        payload = AnalyzeResultPayload.from_dict(data)

        assert payload.project_id == "proj_123"
        assert payload.job_id == "proj_123-brand-0"
        assert payload.batch_size == 50
        assert payload.success_count == 48
        assert payload.error_count == 2

    def test_from_dict_nested_format_legacy(self):
        """Test creating payload from nested dictionary (legacy format)."""
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

        payload = AnalyzeResultPayload.from_dict(data)

        assert payload.project_id == "proj_123"
        assert payload.batch_size == 50
        assert len(payload._results) == 1
        assert payload._results[0].content_id == "v1"
        assert len(payload._errors) == 1

    def test_project_id_required(self):
        """Test that project_id is required (str type)."""
        payload = AnalyzeResultPayload(project_id="", job_id="job-1")
        assert payload.project_id == ""  # Empty string allowed at dataclass level
        # Validation happens at publisher level


class TestAnalyzeResultMessageDeprecated:
    """Tests for deprecated AnalyzeResultMessage wrapper."""

    def test_deprecation_warning(self):
        """Test that using AnalyzeResultMessage raises deprecation warning."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            msg = AnalyzeResultMessage(success=True, payload=payload)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

    def test_to_dict_nested_format(self):
        """Test that deprecated wrapper still produces nested format."""
        payload = AnalyzeResultPayload(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            msg = AnalyzeResultMessage(success=True, payload=payload)
            result = msg.to_dict()

        assert result["success"] is True
        assert "payload" in result
        assert result["payload"]["project_id"] == "proj_123"

    def test_from_dict_flat_format(self):
        """Test creating deprecated message from flat format."""
        data = {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 48,
            "error_count": 2,
        }

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            msg = AnalyzeResultMessage.from_dict(data)

        assert msg.success is True  # Calculated from counts
        assert msg.payload.project_id == "proj_123"

    def test_from_dict_nested_format(self):
        """Test creating deprecated message from nested format."""
        data = {
            "success": True,
            "payload": {
                "project_id": "proj_123",
                "job_id": "proj_123-brand-0",
                "task_type": "analyze_result",
                "batch_size": 50,
                "success_count": 48,
                "error_count": 2,
            },
        }

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            msg = AnalyzeResultMessage.from_dict(data)

        assert msg.success is True
        assert msg.payload.project_id == "proj_123"


class TestFactoryFunctions:
    """Tests for factory functions returning flat AnalyzeResultPayload."""

    def test_create_success_result(self):
        """Test create_success_result returns flat payload."""
        payload = create_success_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
            results=[AnalyzeItem(content_id="v1")],
            errors=[AnalyzeError(content_id="v2", error="Failed")],
        )

        # Returns AnalyzeResultPayload directly (not wrapped)
        assert isinstance(payload, AnalyzeResultPayload)
        assert payload.task_type == "analyze_result"
        assert payload.batch_size == 50
        assert payload.success_count == 48
        assert payload.error_count == 2
        # Internal fields preserved
        assert len(payload._results) == 1
        assert len(payload._errors) == 1

    def test_create_success_result_to_dict_flat(self):
        """Test create_success_result produces flat dict."""
        payload = create_success_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )

        result = payload.to_dict()

        # Flat format, no wrapper
        assert "success" not in result
        assert "payload" not in result
        assert result["project_id"] == "proj_123"
        assert result["batch_size"] == 50

    def test_create_error_result(self):
        """Test create_error_result returns flat payload."""
        payload = create_error_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            error_message="MinIO fetch failed: connection timeout",
        )

        assert isinstance(payload, AnalyzeResultPayload)
        assert payload.task_type == "analyze_result"
        assert payload.batch_size == 50
        assert payload.success_count == 0
        assert payload.error_count == 50
        assert payload._results == []
        assert len(payload._errors) == 1
        assert payload._errors[0].content_id == "batch"
        assert "MinIO fetch failed" in payload._errors[0].error

    def test_create_error_result_to_dict_flat(self):
        """Test create_error_result produces flat dict."""
        payload = create_error_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            error_message="Test error",
        )

        result = payload.to_dict()

        # Flat format
        assert result == {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 0,
            "error_count": 50,
        }
        # No errors array in output (internal only)
        assert "errors" not in result

    def test_create_error_result_empty_project_id(self):
        """Test create_error_result with empty project_id."""
        payload = create_error_result(
            project_id="",
            job_id="550e8400-e29b-41d4-a716-446655440000",
            batch_size=20,
            error_message="Test error",
        )

        # Empty string allowed at dataclass level
        # Validation happens at publisher level
        assert payload.project_id == ""
        assert payload.job_id == "550e8400-e29b-41d4-a716-446655440000"

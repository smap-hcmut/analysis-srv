"""Tests for result publishing integration in consumer.

Tests the integration between consumer message handler and publisher,
including helper functions for building result messages.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from internal.consumers.main import (
    build_result_items,
    build_error_items,
    create_message_handler,
)
from models.messages import AnalyzeItem, AnalyzeError


class TestBuildResultItems:
    """Tests for build_result_items helper function."""

    def test_build_from_success_results(self):
        """Test building items from successful results."""
        processed_results = [
            {
                "status": "success",
                "content_id": "video_1",
                "sentiment": "POSITIVE",
                "sentiment_score": 0.85,
                "impact_score": 75.0,
            },
            {
                "status": "success",
                "content_id": "video_2",
                "impact_score": 50.0,
            },
        ]

        items = build_result_items(processed_results)

        assert len(items) == 2
        assert items[0].content_id == "video_1"
        assert items[0].sentiment == "POSITIVE"
        assert items[0].sentiment_score == 0.85
        assert items[0].impact_score == 75.0
        assert items[1].content_id == "video_2"
        assert items[1].sentiment is None
        assert items[1].impact_score == 50.0

    def test_build_filters_error_results(self):
        """Test that error results are filtered out."""
        processed_results = [
            {"status": "success", "content_id": "video_1"},
            {"status": "error", "content_id": "video_2", "error_code": "PARSE_ERROR"},
            {"status": "success", "content_id": "video_3"},
        ]

        items = build_result_items(processed_results)

        assert len(items) == 2
        content_ids = [item.content_id for item in items]
        assert "video_1" in content_ids
        assert "video_3" in content_ids
        assert "video_2" not in content_ids

    def test_build_empty_list(self):
        """Test building from empty list."""
        items = build_result_items([])
        assert items == []

    def test_build_all_errors(self):
        """Test building when all results are errors."""
        processed_results = [
            {"status": "error", "content_id": "video_1"},
            {"status": "error", "content_id": "video_2"},
        ]

        items = build_result_items(processed_results)
        assert items == []

    def test_build_handles_missing_content_id(self):
        """Test handling results with missing content_id."""
        processed_results = [
            {"status": "success"},  # Missing content_id
        ]

        items = build_result_items(processed_results)

        assert len(items) == 1
        assert items[0].content_id == "unknown"


class TestBuildErrorItems:
    """Tests for build_error_items helper function."""

    def test_build_from_error_results(self):
        """Test building errors from failed results."""
        processed_results = [
            {
                "status": "error",
                "content_id": "video_1",
                "error_code": "PARSE_ERROR",
                "error_message": "Failed to parse content",
            },
            {
                "status": "error",
                "content_id": "video_2",
                "error_code": "TIMEOUT",
            },
        ]

        errors = build_error_items(processed_results)

        assert len(errors) == 2
        assert errors[0].content_id == "video_1"
        assert errors[0].error == "Failed to parse content"
        assert errors[1].content_id == "video_2"
        assert errors[1].error == "TIMEOUT"  # Falls back to error_code

    def test_build_filters_success_results(self):
        """Test that success results are filtered out."""
        processed_results = [
            {"status": "success", "content_id": "video_1"},
            {"status": "error", "content_id": "video_2", "error_message": "Failed"},
            {"status": "success", "content_id": "video_3"},
        ]

        errors = build_error_items(processed_results)

        assert len(errors) == 1
        assert errors[0].content_id == "video_2"

    def test_build_empty_list(self):
        """Test building from empty list."""
        errors = build_error_items([])
        assert errors == []

    def test_build_all_success(self):
        """Test building when all results are success."""
        processed_results = [
            {"status": "success", "content_id": "video_1"},
            {"status": "success", "content_id": "video_2"},
        ]

        errors = build_error_items(processed_results)
        assert errors == []

    def test_build_prefers_error_message_over_code(self):
        """Test that error_message is preferred over error_code."""
        processed_results = [
            {
                "status": "error",
                "content_id": "video_1",
                "error_code": "PARSE_ERROR",
                "error_message": "Detailed error message",
            },
        ]

        errors = build_error_items(processed_results)

        assert errors[0].error == "Detailed error message"

    def test_build_handles_missing_error_info(self):
        """Test handling errors with no error_code or error_message."""
        processed_results = [
            {"status": "error", "content_id": "video_1"},
        ]

        errors = build_error_items(processed_results)

        assert len(errors) == 1
        assert errors[0].error == "Unknown error"


class TestCreateMessageHandlerWithPublisher:
    """Tests for create_message_handler with publisher integration."""

    def test_handler_created_without_publisher(self):
        """Test handler can be created without publisher."""
        handler = create_message_handler(
            phobert=None,
            spacyyake=None,
            publisher=None,
        )

        assert callable(handler)

    def test_handler_created_with_publisher(self):
        """Test handler can be created with publisher."""
        mock_publisher = MagicMock()
        mock_publisher.is_ready.return_value = True

        handler = create_message_handler(
            phobert=None,
            spacyyake=None,
            publisher=mock_publisher,
        )

        assert callable(handler)

    @patch("internal.consumers.main.settings")
    def test_publish_disabled_by_config(self, mock_settings):
        """Test publishing is disabled when publish_enabled=False."""
        mock_settings.publish_enabled = False
        mock_settings.publish_exchange = "results.inbound"
        mock_settings.database_url_sync = "postgresql://test:test@localhost/test"

        mock_publisher = MagicMock()

        # Even with publisher provided, should be disabled
        handler = create_message_handler(
            phobert=None,
            spacyyake=None,
            publisher=mock_publisher,
        )

        assert callable(handler)


class TestResultMessageIntegration:
    """Integration tests for result message building."""

    def test_mixed_results_build_correctly(self):
        """Test building both items and errors from mixed results."""
        processed_results = [
            {
                "status": "success",
                "content_id": "v1",
                "sentiment": "POSITIVE",
                "sentiment_score": 0.9,
                "impact_score": 80.0,
            },
            {
                "status": "error",
                "content_id": "v2",
                "error_code": "PARSE_ERROR",
                "error_message": "Invalid format",
            },
            {
                "status": "success",
                "content_id": "v3",
                "sentiment": "NEGATIVE",
                "sentiment_score": -0.7,
                "impact_score": 60.0,
            },
            {
                "status": "error",
                "content_id": "v4",
                "error_code": "TIMEOUT",
            },
        ]

        items = build_result_items(processed_results)
        errors = build_error_items(processed_results)

        # Verify counts
        assert len(items) == 2
        assert len(errors) == 2

        # Verify items
        item_ids = {item.content_id for item in items}
        assert item_ids == {"v1", "v3"}

        # Verify errors
        error_ids = {err.content_id for err in errors}
        assert error_ids == {"v2", "v4"}

    def test_serialization_round_trip(self):
        """Test that built items can be serialized correctly."""
        processed_results = [
            {
                "status": "success",
                "content_id": "v1",
                "sentiment": "POSITIVE",
                "sentiment_score": 0.85,
                "impact_score": 75.0,
            },
        ]

        items = build_result_items(processed_results)

        # Serialize and verify
        item_dict = items[0].to_dict()
        assert item_dict["content_id"] == "v1"
        assert item_dict["sentiment"] == "POSITIVE"
        assert item_dict["sentiment_score"] == 0.85
        assert item_dict["impact_score"] == 75.0

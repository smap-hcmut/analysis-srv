"""Unit tests for AnalyticsRepository.

These tests focus on project_id sanitization functionality.
"""

import pytest
from unittest.mock import MagicMock, patch

from repository.analytics_repository import AnalyticsRepository, AnalyticsRepositoryError


class TestAnalyticsRepositorySanitizeProjectId:
    """Tests for project_id sanitization in AnalyticsRepository."""

    def test_valid_uuid_passes_through(self):
        """Valid UUID should not be modified."""
        mock_db = MagicMock()
        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80",
        }

        repo._sanitize_project_id(analytics_data)

        assert analytics_data["project_id"] == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_uuid_with_competitor_suffix_sanitized(self):
        """UUID with -competitor suffix should be sanitized."""
        mock_db = MagicMock()
        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor",
        }

        repo._sanitize_project_id(analytics_data)

        assert analytics_data["project_id"] == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_uuid_with_competitor_name_suffix_sanitized(self):
        """UUID with -competitor-name suffix should be sanitized."""
        mock_db = MagicMock()
        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor-Misa",
        }

        repo._sanitize_project_id(analytics_data)

        assert analytics_data["project_id"] == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_invalid_project_id_raises_error(self):
        """Invalid project_id without UUID should raise ValueError."""
        mock_db = MagicMock()
        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": "invalid-string",
        }

        with pytest.raises(ValueError, match="Invalid project_id format"):
            repo._sanitize_project_id(analytics_data)

    def test_none_project_id_passes(self):
        """None project_id should not raise error."""
        mock_db = MagicMock()
        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": None,
        }

        repo._sanitize_project_id(analytics_data)

        assert analytics_data["project_id"] is None

    def test_missing_project_id_passes(self):
        """Missing project_id should not raise error."""
        mock_db = MagicMock()
        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
        }

        repo._sanitize_project_id(analytics_data)

        assert "project_id" not in analytics_data


class TestAnalyticsRepositorySaveWithSanitization:
    """Tests for save method with project_id sanitization."""

    def test_save_sanitizes_invalid_project_id(self):
        """Save should sanitize invalid project_id before persisting."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = None

        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor",
            "platform": "TIKTOK",
        }

        repo.save(analytics_data)

        # Verify the data was sanitized before add
        call_args = mock_db.add.call_args[0][0]
        assert call_args.project_id == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_save_with_valid_project_id(self):
        """Save should work normally with valid project_id."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = None

        repo = AnalyticsRepository(mock_db)

        analytics_data = {
            "id": "post_123",
            "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80",
            "platform": "TIKTOK",
        }

        repo.save(analytics_data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestAnalyticsRepositorySaveBatchWithSanitization:
    """Tests for save_batch method with project_id sanitization."""

    def test_save_batch_sanitizes_invalid_project_ids(self):
        """save_batch should sanitize invalid project_ids."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = None

        repo = AnalyticsRepository(mock_db)

        records = [
            {
                "id": "post_1",
                "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor",
                "platform": "TIKTOK",
            },
            {
                "id": "post_2",
                "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80",
                "platform": "TIKTOK",
            },
        ]

        repo.save_batch(records)

        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

    def test_save_batch_skips_invalid_records(self):
        """save_batch should skip records with completely invalid project_id."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.one_or_none.return_value = None

        repo = AnalyticsRepository(mock_db)

        records = [
            {
                "id": "post_1",
                "project_id": "invalid-string",  # Will be skipped
                "platform": "TIKTOK",
            },
            {
                "id": "post_2",
                "project_id": "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80",
                "platform": "TIKTOK",
            },
        ]

        repo.save_batch(records)

        # Only one record should be added (the valid one)
        assert mock_db.add.call_count == 1

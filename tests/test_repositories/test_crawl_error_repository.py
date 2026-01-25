"""Unit tests for CrawlErrorRepository.

These tests use mocking to avoid database dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from repository.crawl_error_repository import (
    CrawlErrorRepository,
    CrawlErrorRepositoryError,
)
from models.database import CrawlError
from core.constants import ErrorCategory


class TestCrawlErrorRepositorySave:
    """Tests for CrawlErrorRepository.save method."""

    def test_save_valid_error(self):
        """Save a valid error record."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_data = {
            "content_id": "post_123",
            "project_id": "550e8400-e29b-41d4-a716-446655440000",
            "job_id": "proj_abc-brand-0",
            "platform": "tiktok",
            "error_code": "RATE_LIMITED",
            "error_message": "Too many requests",
        }

        result = repo.save(error_data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_save_missing_content_id_raises_error(self):
        """Save without content_id should raise ValueError."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_data = {
            "job_id": "proj_abc-brand-0",
            "platform": "tiktok",
            "error_code": "RATE_LIMITED",
        }

        with pytest.raises(ValueError, match="content_id"):
            repo.save(error_data)

    def test_save_missing_job_id_raises_error(self):
        """Save without job_id should raise ValueError."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_data = {
            "content_id": "post_123",
            "platform": "tiktok",
            "error_code": "RATE_LIMITED",
        }

        with pytest.raises(ValueError, match="job_id"):
            repo.save(error_data)

    def test_save_missing_platform_raises_error(self):
        """Save without platform should raise ValueError."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_data = {
            "content_id": "post_123",
            "job_id": "proj_abc-brand-0",
            "error_code": "RATE_LIMITED",
        }

        with pytest.raises(ValueError, match="platform"):
            repo.save(error_data)

    def test_save_missing_error_code_raises_error(self):
        """Save without error_code should raise ValueError."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_data = {
            "content_id": "post_123",
            "job_id": "proj_abc-brand-0",
            "platform": "tiktok",
        }

        with pytest.raises(ValueError, match="error_code"):
            repo.save(error_data)

    def test_save_auto_categorizes_error(self):
        """Save should auto-categorize error code."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_data = {
            "content_id": "post_123",
            "job_id": "proj_abc-brand-0",
            "platform": "tiktok",
            "error_code": "NETWORK_ERROR",
        }

        repo.save(error_data)

        # Verify the CrawlError was created with correct category
        call_args = mock_db.add.call_args[0][0]
        assert call_args.error_category == ErrorCategory.NETWORK.value


class TestCrawlErrorRepositorySaveBatch:
    """Tests for CrawlErrorRepository.save_batch method."""

    def test_save_batch_empty_list(self):
        """Save empty batch should return empty list."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        result = repo.save_batch([])

        assert result == []
        mock_db.commit.assert_not_called()

    def test_save_batch_multiple_records(self):
        """Save multiple error records in batch."""
        mock_db = MagicMock()
        repo = CrawlErrorRepository(mock_db)

        error_records = [
            {
                "content_id": "post_1",
                "job_id": "proj_abc-brand-0",
                "platform": "tiktok",
                "error_code": "RATE_LIMITED",
            },
            {
                "content_id": "post_2",
                "job_id": "proj_abc-brand-0",
                "platform": "tiktok",
                "error_code": "CONTENT_REMOVED",
            },
        ]

        repo.save_batch(error_records)

        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()


class TestCrawlErrorRepositoryGetErrorStats:
    """Tests for CrawlErrorRepository.get_error_stats method."""

    def test_get_error_stats_returns_structure(self):
        """get_error_stats should return correct structure."""
        mock_db = MagicMock()

        # Mock query chain
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.all.return_value = [("RATE_LIMITED", 5), ("NETWORK_ERROR", 3)]

        repo = CrawlErrorRepository(mock_db)
        result = repo.get_error_stats()

        assert "total_errors" in result
        assert "by_code" in result
        assert "by_category" in result
        assert "by_platform" in result

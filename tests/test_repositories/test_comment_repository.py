"""Unit tests for CommentRepository.

Tests for comment persistence operations (Contract v2.0).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from repository.comment_repository import CommentRepository, CommentRepositoryError
from models.database import PostComment


class TestCommentRepositorySave:
    """Tests for CommentRepository.save() method."""

    def test_save_creates_comment_record(self):
        """save() should create a comment record in database."""
        mock_db = MagicMock()
        repo = CommentRepository(mock_db)

        comment_data = {
            "post_id": "post_123",
            "comment_id": "cmt_001",
            "text": "Great video!",
            "author_name": "User123",
            "likes": 10,
            "commented_at": datetime(2025, 12, 10, 10, 0, 0, tzinfo=timezone.utc),
        }

        repo.save(comment_data)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_save_requires_post_id(self):
        """save() should raise ValueError if post_id is missing."""
        mock_db = MagicMock()
        repo = CommentRepository(mock_db)

        comment_data = {
            "text": "Great video!",
            "author_name": "User123",
        }

        with pytest.raises(ValueError, match="post_id"):
            repo.save(comment_data)

    def test_save_requires_text(self):
        """save() should raise ValueError if text is missing."""
        mock_db = MagicMock()
        repo = CommentRepository(mock_db)

        comment_data = {
            "post_id": "post_123",
            "author_name": "User123",
        }

        with pytest.raises(ValueError, match="text"):
            repo.save(comment_data)

    def test_save_handles_database_error(self):
        """save() should raise CommentRepositoryError on database failure."""
        mock_db = MagicMock()
        mock_db.commit.side_effect = SQLAlchemyError("Database connection lost")
        repo = CommentRepository(mock_db)

        comment_data = {
            "post_id": "post_123",
            "text": "Great video!",
        }

        with pytest.raises(CommentRepositoryError, match="Failed to save comment"):
            repo.save(comment_data)

        mock_db.rollback.assert_called_once()


class TestCommentRepositorySaveBatch:
    """Tests for CommentRepository.save_batch() method."""

    def test_save_batch_creates_multiple_records(self):
        """save_batch() should create multiple comment records."""
        mock_db = MagicMock()
        repo = CommentRepository(mock_db)

        comments = [
            {"post_id": "post_123", "text": "Comment 1", "author_name": "User1"},
            {"post_id": "post_123", "text": "Comment 2", "author_name": "User2"},
            {"post_id": "post_123", "text": "Comment 3", "author_name": "User3"},
        ]

        repo.save_batch(comments)

        assert mock_db.add.call_count == 3
        mock_db.commit.assert_called_once()

    def test_save_batch_skips_invalid_comments(self):
        """save_batch() should skip comments without required fields."""
        mock_db = MagicMock()
        repo = CommentRepository(mock_db)

        comments = [
            {"post_id": "post_123", "text": "Valid comment"},
            {"post_id": "post_123"},  # Missing text - should be skipped
            {"text": "No post_id"},  # Missing post_id - should be skipped
            {"post_id": "post_123", "text": "Another valid"},
        ]

        repo.save_batch(comments)

        # Only 2 valid comments should be added
        assert mock_db.add.call_count == 2

    def test_save_batch_empty_list(self):
        """save_batch() should handle empty list gracefully."""
        mock_db = MagicMock()
        repo = CommentRepository(mock_db)

        result = repo.save_batch([])

        assert result == []
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    def test_save_batch_handles_database_error(self):
        """save_batch() should raise CommentRepositoryError on database failure."""
        mock_db = MagicMock()
        mock_db.commit.side_effect = SQLAlchemyError("Database error")
        repo = CommentRepository(mock_db)

        comments = [
            {"post_id": "post_123", "text": "Comment 1"},
        ]

        with pytest.raises(CommentRepositoryError, match="Failed to save comment batch"):
            repo.save_batch(comments)

        mock_db.rollback.assert_called_once()


class TestCommentRepositoryGetByPostId:
    """Tests for CommentRepository.get_by_post_id() method."""

    def test_get_by_post_id_returns_comments(self):
        """get_by_post_id() should return comments for a post."""
        mock_db = MagicMock()
        mock_comments = [
            MagicMock(spec=PostComment, post_id="post_123", text="Comment 1"),
            MagicMock(spec=PostComment, post_id="post_123", text="Comment 2"),
        ]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            mock_comments
        )

        repo = CommentRepository(mock_db)
        result = repo.get_by_post_id("post_123")

        assert len(result) == 2
        mock_db.query.assert_called_once_with(PostComment)

    def test_get_by_post_id_returns_empty_list(self):
        """get_by_post_id() should return empty list if no comments found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        repo = CommentRepository(mock_db)
        result = repo.get_by_post_id("post_nonexistent")

        assert result == []


class TestCommentRepositoryDeleteByPostId:
    """Tests for CommentRepository.delete_by_post_id() method."""

    def test_delete_by_post_id_removes_comments(self):
        """delete_by_post_id() should delete all comments for a post."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = 5

        repo = CommentRepository(mock_db)
        count = repo.delete_by_post_id("post_123")

        assert count == 5
        mock_db.commit.assert_called_once()

    def test_delete_by_post_id_handles_database_error(self):
        """delete_by_post_id() should raise CommentRepositoryError on failure."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.side_effect = SQLAlchemyError(
            "DB error"
        )

        repo = CommentRepository(mock_db)

        with pytest.raises(CommentRepositoryError, match="Failed to delete comments"):
            repo.delete_by_post_id("post_123")

        mock_db.rollback.assert_called_once()


class TestCommentRepositoryCountByPostId:
    """Tests for CommentRepository.count_by_post_id() method."""

    def test_count_by_post_id_returns_count(self):
        """count_by_post_id() should return number of comments."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 10

        repo = CommentRepository(mock_db)
        count = repo.count_by_post_id("post_123")

        assert count == 10

    def test_count_by_post_id_returns_zero(self):
        """count_by_post_id() should return 0 if no comments."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 0

        repo = CommentRepository(mock_db)
        count = repo.count_by_post_id("post_nonexistent")

        assert count == 0

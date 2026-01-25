"""Repository for persisting post comments to the database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.logger import logger
from models.database import PostComment


class CommentRepositoryError(Exception):
    """Base exception for comment repository operations."""

    pass


class CommentRepository:
    """Repository abstraction for `PostComment` operations.

    This class provides a clean interface for persisting and retrieving
    comment data, abstracting away SQLAlchemy details.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db

    def save(self, comment_data: Dict[str, Any]) -> PostComment:
        """Save a single comment to the database.

        Args:
            comment_data: Dictionary containing comment fields.

        Returns:
            The persisted PostComment instance.

        Raises:
            CommentRepositoryError: If database operation fails.
            ValueError: If comment_data is missing required fields.
        """
        post_id = comment_data.get("post_id")
        text = comment_data.get("text")

        if not post_id:
            raise ValueError("comment_data must contain 'post_id' field")
        if not text:
            raise ValueError("comment_data must contain 'text' field")

        try:
            comment = PostComment(**comment_data)
            self.db.add(comment)
            self.db.commit()
            self.db.refresh(comment)
            logger.debug(f"Saved comment for post_id={post_id}")
            return comment

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error saving comment for post_id={post_id}: {exc}")
            raise CommentRepositoryError(f"Failed to save comment: {exc}") from exc

    def save_batch(self, comments: List[Dict[str, Any]]) -> List[PostComment]:
        """Save multiple comments in a single transaction.

        Args:
            comments: List of comment data dictionaries.

        Returns:
            List of persisted PostComment instances.

        Raises:
            CommentRepositoryError: If database operation fails.
        """
        if not comments:
            return []

        try:
            saved_comments = []
            for comment_data in comments:
                post_id = comment_data.get("post_id")
                text = comment_data.get("text")

                if not post_id or not text:
                    logger.warning(
                        f"Skipping comment without required fields: post_id={post_id}, has_text={bool(text)}"
                    )
                    continue

                comment = PostComment(**comment_data)
                self.db.add(comment)
                saved_comments.append(comment)

            self.db.commit()

            for comment in saved_comments:
                self.db.refresh(comment)

            logger.debug(f"Saved {len(saved_comments)} comments in batch")
            return saved_comments

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error saving comment batch: {exc}")
            raise CommentRepositoryError(f"Failed to save comment batch: {exc}") from exc

    def get_by_post_id(self, post_id: str) -> List[PostComment]:
        """Get all comments for a specific post.

        Args:
            post_id: The post ID to filter by.

        Returns:
            List of PostComment instances.
        """
        return (
            self.db.query(PostComment)
            .filter(PostComment.post_id == post_id)
            .order_by(PostComment.commented_at.desc())
            .all()
        )

    def delete_by_post_id(self, post_id: str) -> int:
        """Delete all comments for a specific post.

        Args:
            post_id: The post ID to delete comments for.

        Returns:
            Number of deleted comments.

        Raises:
            CommentRepositoryError: If database operation fails.
        """
        try:
            count = self.db.query(PostComment).filter(PostComment.post_id == post_id).delete()
            self.db.commit()
            logger.debug(f"Deleted {count} comments for post_id={post_id}")
            return count

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error deleting comments for post_id={post_id}: {exc}")
            raise CommentRepositoryError(f"Failed to delete comments: {exc}") from exc

    def count_by_post_id(self, post_id: str) -> int:
        """Count comments for a specific post.

        Args:
            post_id: The post ID to count comments for.

        Returns:
            Number of comments.
        """
        return self.db.query(PostComment).filter(PostComment.post_id == post_id).count()

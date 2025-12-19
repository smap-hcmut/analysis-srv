"""Repository for persisting analytics results to the database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.logger import logger
from models.database import PostAnalytics
from utils.uuid_utils import extract_uuid, is_valid_uuid
from utils.json_encoder import sanitize_analytics_data


class AnalyticsRepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class AnalyticsRepository:
    """Repository abstraction for `PostAnalytics` operations.

    This class provides a clean interface for persisting and retrieving
    analytics data, abstracting away SQLAlchemy details from the orchestrator.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db

    def _sanitize_project_id(self, analytics_data: Dict[str, Any]) -> None:
        """Sanitize project_id field to ensure valid UUID format.

        If project_id contains extra characters (e.g., "uuid-competitor"),
        extracts the valid UUID portion. Modifies analytics_data in place.

        Args:
            analytics_data: Dictionary containing analytics fields.

        Raises:
            ValueError: If project_id is present but contains no valid UUID.
        """
        project_id = analytics_data.get("project_id")
        if not project_id:
            return

        if is_valid_uuid(project_id):
            return

        # Try to extract valid UUID from malformed value
        sanitized = extract_uuid(project_id)
        if sanitized:
            logger.warning(f"Sanitized invalid project_id: {project_id} -> {sanitized}")
            analytics_data["project_id"] = sanitized
        else:
            raise ValueError(f"Invalid project_id format, cannot extract UUID: {project_id}")

    def save(self, analytics_data: Dict[str, Any]) -> PostAnalytics:
        """Save analytics result into the `post_analytics` table.

        This method performs an insert-or-update (upsert-like) behavior based on
        the primary key `id`, so re-processing the same post overwrites the
        previous analytics record.

        Args:
            analytics_data: Dictionary containing analytics fields matching PostAnalytics model.

        Returns:
            The persisted PostAnalytics instance.

        Raises:
            AnalyticsRepositoryError: If database operation fails.
            ValueError: If analytics_data is missing required 'id' field.
        """
        # Sanitize data: fix NULL strings, boolean strings, ensure ID is string
        analytics_data = sanitize_analytics_data(analytics_data)

        post_id = analytics_data.get("id")
        if not post_id:
            raise ValueError("analytics_data must contain 'id' field")

        # Sanitize project_id to ensure valid UUID format
        self._sanitize_project_id(analytics_data)

        try:
            existing = self.get_by_id(post_id)

            if existing is None:
                post = PostAnalytics(**analytics_data)
                self.db.add(post)
                logger.debug(f"Creating new PostAnalytics record: id={post_id}")
            else:
                post = existing
                for key, value in analytics_data.items():
                    if hasattr(post, key):
                        setattr(post, key, value)
                logger.debug(f"Updating existing PostAnalytics record: id={post_id}")

            self.db.commit()
            self.db.refresh(post)
            return post

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.opt(exception=True).error(
                f"Database error saving analytics for post_id={post_id}: {exc}"
            )
            raise AnalyticsRepositoryError(f"Failed to save analytics: {exc}") from exc

    def get_by_id(self, post_id: str) -> Optional[PostAnalytics]:
        """Fetch a `PostAnalytics` record by its primary key.

        Args:
            post_id: The primary key of the post.

        Returns:
            PostAnalytics instance if found, None otherwise.
        """
        return self.db.query(PostAnalytics).filter(PostAnalytics.id == post_id).one_or_none()

    def get_by_project(
        self, project_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[PostAnalytics]:
        """Fetch analytics records for a specific project.

        Args:
            project_id: The project UUID to filter by.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of PostAnalytics instances.
        """
        return (
            self.db.query(PostAnalytics)
            .filter(PostAnalytics.project_id == project_id)
            .order_by(PostAnalytics.analyzed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def delete_by_id(self, post_id: str) -> bool:
        """Delete a PostAnalytics record by its primary key.

        Args:
            post_id: The primary key of the post to delete.

        Returns:
            True if record was deleted, False if not found.
        """
        try:
            result = self.db.query(PostAnalytics).filter(PostAnalytics.id == post_id).delete()
            self.db.commit()
            return result > 0
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error deleting post_id={post_id}: {exc}")
            raise AnalyticsRepositoryError(f"Failed to delete analytics: {exc}") from exc

    def save_batch(self, analytics_records: List[Dict[str, Any]]) -> List[PostAnalytics]:
        """Save multiple analytics records in a single transaction.

        This method is optimized for batch processing from crawler events.

        Args:
            analytics_records: List of analytics data dictionaries.

        Returns:
            List of persisted PostAnalytics instances.

        Raises:
            AnalyticsRepositoryError: If database operation fails.
        """
        if not analytics_records:
            return []

        try:
            saved_records = []
            for analytics_data in analytics_records:
                # Sanitize data: fix NULL strings, boolean strings, ensure ID is string
                analytics_data = sanitize_analytics_data(analytics_data)

                post_id = analytics_data.get("id")
                if not post_id:
                    logger.warning("Skipping record without 'id' field")
                    continue

                # Sanitize project_id to ensure valid UUID format
                try:
                    self._sanitize_project_id(analytics_data)
                except ValueError as e:
                    logger.warning(f"Skipping record with invalid project_id: {e}")
                    continue

                existing = self.get_by_id(post_id)
                if existing is None:
                    post = PostAnalytics(**analytics_data)
                    self.db.add(post)
                else:
                    post = existing
                    for key, value in analytics_data.items():
                        if hasattr(post, key):
                            setattr(post, key, value)
                saved_records.append(post)

            self.db.commit()

            for record in saved_records:
                self.db.refresh(record)

            logger.debug(f"Saved {len(saved_records)} analytics records in batch")
            return saved_records

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error saving batch of analytics: {exc}")
            raise AnalyticsRepositoryError(f"Failed to save analytics batch: {exc}") from exc

    def get_by_job_id(
        self, job_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[PostAnalytics]:
        """Fetch analytics records for a specific job.

        Args:
            job_id: The job identifier to filter by.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of PostAnalytics instances.
        """
        return (
            self.db.query(PostAnalytics)
            .filter(PostAnalytics.job_id == job_id)
            .order_by(PostAnalytics.analyzed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_by_fetch_status(
        self, fetch_status: str, *, limit: int = 100, offset: int = 0
    ) -> List[PostAnalytics]:
        """Fetch analytics records by fetch status.

        Args:
            fetch_status: The fetch status to filter by ('success' or 'error').
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of PostAnalytics instances.
        """
        return (
            self.db.query(PostAnalytics)
            .filter(PostAnalytics.fetch_status == fetch_status)
            .order_by(PostAnalytics.analyzed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count_by_job_id(self, job_id: str) -> Dict[str, int]:
        """Count analytics records by fetch status for a job.

        Args:
            job_id: The job identifier.

        Returns:
            Dictionary with counts: {'total': int, 'success': int, 'error': int}
        """
        total = self.db.query(PostAnalytics).filter(PostAnalytics.job_id == job_id).count()
        success = (
            self.db.query(PostAnalytics)
            .filter(PostAnalytics.job_id == job_id)
            .filter(PostAnalytics.fetch_status == "success")
            .count()
        )
        error = (
            self.db.query(PostAnalytics)
            .filter(PostAnalytics.job_id == job_id)
            .filter(PostAnalytics.fetch_status == "error")
            .count()
        )
        return {"total": total, "success": success, "error": error}

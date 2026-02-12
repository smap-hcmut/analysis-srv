"""Repository for persisting analyzed posts to the database."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pkg.logger.logger import Logger
from internal.model import AnalyzedPost


class AnalyzedPostRepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class AnalyzedPostRepository:
    """Repository abstraction for `AnalyzedPost` operations.

    This class provides a clean interface for persisting and retrieving
    analytics data, abstracting away SQLAlchemy details from the orchestrator.
    """

    def __init__(self, db: Session, logger: Optional[Logger] = None) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations
            logger: Logger instance (optional)
        """
        self.db = db
        self.logger = logger

    def _is_valid_uuid(self, value: str) -> bool:
        """Check if string is valid UUID.
        
        Args:
            value: String to validate
            
        Returns:
            True if valid UUID, False otherwise
        """
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))

    def _extract_uuid(self, value: str) -> Optional[str]:
        """Extract UUID from string.
        
        Args:
            value: String potentially containing UUID
            
        Returns:
            Extracted UUID or None
        """
        uuid_pattern = re.compile(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            re.IGNORECASE
        )
        match = uuid_pattern.search(value)
        return match.group(0) if match else None

    def _sanitize_project_id(self, analytics_data: Dict[str, Any]) -> None:
        """Sanitize project_id field to ensure valid UUID format.

        If project_id contains extra characters (e.g., "uuid-competitor"),
        extracts the valid UUID portion. Modifies analytics_data in place.

        Args:
            analytics_data: Dictionary containing analytics fields

        Raises:
            ValueError: If project_id is present but contains no valid UUID
        """
        project_id = analytics_data.get("project_id")
        if not project_id:
            return

        if self._is_valid_uuid(project_id):
            return

        # Try to extract valid UUID from malformed value
        sanitized = self._extract_uuid(project_id)
        if sanitized:
            if self.logger:
                self.logger.warning(
                    f"Sanitized invalid project_id: {project_id} -> {sanitized}"
                )
            analytics_data["project_id"] = sanitized
        else:
            raise ValueError(
                f"Invalid project_id format, cannot extract UUID: {project_id}"
            )

    def _sanitize_data(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize analytics data.
        
        Args:
            analytics_data: Raw analytics data
            
        Returns:
            Sanitized analytics data
        """
        sanitized = analytics_data.copy()
        
        # Convert string "NULL" to None
        for key, value in sanitized.items():
            if isinstance(value, str) and value.upper() == "NULL":
                sanitized[key] = None
        
        # Ensure id is string
        if "id" in sanitized and sanitized["id"] is not None:
            sanitized["id"] = str(sanitized["id"])
        
        return sanitized

    def save(self, analytics_data: Dict[str, Any]) -> AnalyzedPost:
        """Save analytics result into the `post_analytics` table.

        This method performs an insert-or-update (upsert-like) behavior based on
        the primary key `id`, so re-processing the same post overwrites the
        previous analytics record.

        Args:
            analytics_data: Dictionary containing analytics fields matching AnalyzedPost model

        Returns:
            The persisted AnalyzedPost instance

        Raises:
            AnalyzedPostRepositoryError: If database operation fails
            ValueError: If analytics_data is missing required 'id' field
        """
        # Sanitize data
        analytics_data = self._sanitize_data(analytics_data)

        post_id = analytics_data.get("id")
        if not post_id:
            raise ValueError("analytics_data must contain 'id' field")

        # Sanitize project_id to ensure valid UUID format
        self._sanitize_project_id(analytics_data)

        try:
            existing = self.get_by_id(post_id)

            if existing is None:
                post = AnalyzedPost(**analytics_data)
                self.db.add(post)
                if self.logger:
                    self.logger.debug(f"Creating new AnalyzedPost record: id={post_id}")
            else:
                post = existing
                for key, value in analytics_data.items():
                    if hasattr(post, key):
                        setattr(post, key, value)
                if self.logger:
                    self.logger.debug(f"Updating existing AnalyzedPost record: id={post_id}")

            self.db.commit()
            self.db.refresh(post)
            return post

        except SQLAlchemyError as exc:
            self.db.rollback()
            if self.logger:
                self.logger.error(
                    f"Database error saving analytics for post_id={post_id}: {exc}"
                )
            raise AnalyzedPostRepositoryError(f"Failed to save analytics: {exc}") from exc

    def get_by_id(self, post_id: str) -> Optional[AnalyzedPost]:
        """Fetch a `AnalyzedPost` record by its primary key.

        Args:
            post_id: The primary key of the post

        Returns:
            AnalyzedPost instance if found, None otherwise
        """
        return self.db.query(AnalyzedPost).filter(AnalyzedPost.id == post_id).one_or_none()

    def get_by_project(
        self, project_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[AnalyzedPost]:
        """Fetch analytics records for a specific project.

        Args:
            project_id: The project UUID to filter by
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of AnalyzedPost instances
        """
        return (
            self.db.query(AnalyzedPost)
            .filter(AnalyzedPost.project_id == project_id)
            .order_by(AnalyzedPost.analyzed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def delete_by_id(self, post_id: str) -> bool:
        """Delete a AnalyzedPost record by its primary key.

        Args:
            post_id: The primary key of the post to delete

        Returns:
            True if record was deleted, False if not found
        """
        try:
            result = self.db.query(AnalyzedPost).filter(AnalyzedPost.id == post_id).delete()
            self.db.commit()
            return result > 0
        except SQLAlchemyError as exc:
            self.db.rollback()
            if self.logger:
                self.logger.error(f"Database error deleting post_id={post_id}: {exc}")
            raise AnalyzedPostRepositoryError(f"Failed to delete analytics: {exc}") from exc

    def save_batch(self, analytics_records: List[Dict[str, Any]]) -> List[AnalyzedPost]:
        """Save multiple analytics records in a single transaction.

        This method is optimized for batch processing from crawler events.

        Args:
            analytics_records: List of analytics data dictionaries

        Returns:
            List of persisted AnalyzedPost instances

        Raises:
            AnalyzedPostRepositoryError: If database operation fails
        """
        if not analytics_records:
            return []

        try:
            saved_records = []
            for analytics_data in analytics_records:
                # Sanitize data
                analytics_data = self._sanitize_data(analytics_data)

                post_id = analytics_data.get("id")
                if not post_id:
                    if self.logger:
                        self.logger.warning("Skipping record without 'id' field")
                    continue

                # Sanitize project_id
                try:
                    self._sanitize_project_id(analytics_data)
                except ValueError as e:
                    if self.logger:
                        self.logger.warning(f"Skipping record with invalid project_id: {e}")
                    continue

                existing = self.get_by_id(post_id)
                if existing is None:
                    post = AnalyzedPost(**analytics_data)
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

            if self.logger:
                self.logger.debug(f"Saved {len(saved_records)} analytics records in batch")
            return saved_records

        except SQLAlchemyError as exc:
            self.db.rollback()
            if self.logger:
                self.logger.error(f"Database error saving batch of analytics: {exc}")
            raise AnalyzedPostRepositoryError(f"Failed to save analytics batch: {exc}") from exc

    def get_by_job_id(
        self, job_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[AnalyzedPost]:
        """Fetch analytics records for a specific job.

        Args:
            job_id: The job identifier to filter by
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of AnalyzedPost instances
        """
        return (
            self.db.query(AnalyzedPost)
            .filter(AnalyzedPost.job_id == job_id)
            .order_by(AnalyzedPost.analyzed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count_by_job_id(self, job_id: str) -> Dict[str, int]:
        """Count analytics records by status for a job.

        Args:
            job_id: The job identifier

        Returns:
            Dictionary with counts: {'total': int, 'success': int, 'error': int}
        """
        total = self.db.query(AnalyzedPost).filter(AnalyzedPost.job_id == job_id).count()
        success = (
            self.db.query(AnalyzedPost)
            .filter(AnalyzedPost.job_id == job_id)
            .filter(AnalyzedPost.processing_status == "success")
            .count()
        )
        error = (
            self.db.query(AnalyzedPost)
            .filter(AnalyzedPost.job_id == job_id)
            .filter(AnalyzedPost.processing_status == "error")
            .count()
        )
        return {"total": total, "success": success, "error": error}


__all__ = ["AnalyticsRepository", "AnalyzedPostRepositoryError"]

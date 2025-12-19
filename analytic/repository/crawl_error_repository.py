"""Repository for persisting crawl error records to the database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.constants import ErrorCategory, categorize_error
from core.logger import logger
from models.database import CrawlError


class CrawlErrorRepositoryError(Exception):
    """Base exception for crawl error repository operations."""

    pass


class CrawlErrorRepository:
    """Repository abstraction for `CrawlError` operations.

    This class provides a clean interface for persisting and retrieving
    crawl error data, enabling error analytics and monitoring.
    """

    def __init__(self, db: Session) -> None:
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy session for database operations.
        """
        self.db = db

    def save(self, error_data: Dict[str, Any]) -> CrawlError:
        """Save a crawl error record into the `crawl_errors` table.

        Args:
            error_data: Dictionary containing error fields:
                - content_id: str (required)
                - project_id: UUID or None
                - job_id: str (required)
                - platform: str (required)
                - error_code: str (required)
                - error_message: str (optional)
                - error_details: dict (optional)
                - permalink: str (optional)

        Returns:
            The persisted CrawlError instance.

        Raises:
            CrawlErrorRepositoryError: If database operation fails.
            ValueError: If required fields are missing.
        """
        required_fields = ["content_id", "job_id", "platform", "error_code"]
        for field in required_fields:
            if not error_data.get(field):
                raise ValueError(f"error_data must contain '{field}' field")

        try:
            # Auto-categorize error code
            error_category = categorize_error(error_data["error_code"])

            error_record = CrawlError(
                content_id=error_data["content_id"],
                project_id=error_data.get("project_id"),
                job_id=error_data["job_id"],
                platform=error_data["platform"],
                error_code=error_data["error_code"],
                error_category=error_category.value,
                error_message=error_data.get("error_message"),
                error_details=error_data.get("error_details"),
                permalink=error_data.get("permalink"),
                created_at=datetime.now(timezone.utc),
            )

            self.db.add(error_record)
            self.db.commit()
            self.db.refresh(error_record)

            logger.debug(
                f"Created CrawlError record: id={error_record.id}, content_id={error_record.content_id}, "
                f"error_code={error_record.error_code}"
            )

            return error_record

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                f"Database error saving crawl error for content_id={error_data.get('content_id')}: {exc}"
            )
            raise CrawlErrorRepositoryError(f"Failed to save crawl error: {exc}") from exc

    def save_batch(self, error_records: List[Dict[str, Any]]) -> List[CrawlError]:
        """Save multiple crawl error records in a single transaction.

        Args:
            error_records: List of error data dictionaries.

        Returns:
            List of persisted CrawlError instances.

        Raises:
            CrawlErrorRepositoryError: If database operation fails.
        """
        if not error_records:
            return []

        try:
            saved_records = []
            for error_data in error_records:
                error_category = categorize_error(error_data.get("error_code", "UNKNOWN_ERROR"))

                error_record = CrawlError(
                    content_id=error_data["content_id"],
                    project_id=error_data.get("project_id"),
                    job_id=error_data["job_id"],
                    platform=error_data["platform"],
                    error_code=error_data.get("error_code", "UNKNOWN_ERROR"),
                    error_category=error_category.value,
                    error_message=error_data.get("error_message"),
                    error_details=error_data.get("error_details"),
                    permalink=error_data.get("permalink"),
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(error_record)
                saved_records.append(error_record)

            self.db.commit()

            for record in saved_records:
                self.db.refresh(record)

            logger.debug(f"Saved {len(saved_records)} crawl error records in batch")
            return saved_records

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error saving batch of crawl errors: {exc}")
            raise CrawlErrorRepositoryError(f"Failed to save crawl errors batch: {exc}") from exc

    def get_by_id(self, error_id: int) -> Optional[CrawlError]:
        """Fetch a CrawlError record by its primary key.

        Args:
            error_id: The primary key of the error record.

        Returns:
            CrawlError instance if found, None otherwise.
        """
        return self.db.query(CrawlError).filter(CrawlError.id == error_id).one_or_none()

    def get_by_job_id(self, job_id: str, *, limit: int = 100, offset: int = 0) -> List[CrawlError]:
        """Fetch error records for a specific job.

        Args:
            job_id: The job identifier to filter by.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of CrawlError instances.
        """
        return (
            self.db.query(CrawlError)
            .filter(CrawlError.job_id == job_id)
            .order_by(CrawlError.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_by_project(
        self, project_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[CrawlError]:
        """Fetch error records for a specific project.

        Args:
            project_id: The project UUID to filter by.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of CrawlError instances.
        """
        return (
            self.db.query(CrawlError)
            .filter(CrawlError.project_id == project_id)
            .order_by(CrawlError.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_error_stats(
        self, project_id: Optional[str] = None, job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get error statistics grouped by error code and category.

        Args:
            project_id: Optional project UUID to filter by.
            job_id: Optional job ID to filter by.

        Returns:
            Dictionary with error statistics:
                - total_errors: int
                - by_code: Dict[str, int]
                - by_category: Dict[str, int]
                - by_platform: Dict[str, int]
        """
        query = self.db.query(CrawlError)

        if project_id:
            query = query.filter(CrawlError.project_id == project_id)
        if job_id:
            query = query.filter(CrawlError.job_id == job_id)

        # Total count
        total_errors = query.count()

        # Group by error_code
        by_code_query = self.db.query(CrawlError.error_code, func.count(CrawlError.id)).group_by(
            CrawlError.error_code
        )
        if project_id:
            by_code_query = by_code_query.filter(CrawlError.project_id == project_id)
        if job_id:
            by_code_query = by_code_query.filter(CrawlError.job_id == job_id)
        by_code = dict(by_code_query.all())

        # Group by error_category
        by_category_query = self.db.query(
            CrawlError.error_category, func.count(CrawlError.id)
        ).group_by(CrawlError.error_category)
        if project_id:
            by_category_query = by_category_query.filter(CrawlError.project_id == project_id)
        if job_id:
            by_category_query = by_category_query.filter(CrawlError.job_id == job_id)
        by_category = dict(by_category_query.all())

        # Group by platform
        by_platform_query = self.db.query(CrawlError.platform, func.count(CrawlError.id)).group_by(
            CrawlError.platform
        )
        if project_id:
            by_platform_query = by_platform_query.filter(CrawlError.project_id == project_id)
        if job_id:
            by_platform_query = by_platform_query.filter(CrawlError.job_id == job_id)
        by_platform = dict(by_platform_query.all())

        return {
            "total_errors": total_errors,
            "by_code": by_code,
            "by_category": by_category,
            "by_platform": by_platform,
        }

    def delete_by_job_id(self, job_id: str) -> int:
        """Delete all error records for a specific job.

        Args:
            job_id: The job identifier.

        Returns:
            Number of records deleted.
        """
        try:
            result = self.db.query(CrawlError).filter(CrawlError.job_id == job_id).delete()
            self.db.commit()
            return result
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(f"Database error deleting errors for job_id={job_id}: {exc}")
            raise CrawlErrorRepositoryError(f"Failed to delete crawl errors: {exc}") from exc

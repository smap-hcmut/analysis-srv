"""Repository for persisting analyzed posts to the database."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from internal.model import AnalyzedPost
from internal.analytics.constant import NULL_STRING, STATUS_SUCCESS, STATUS_ERROR


class AnalyzedPostRepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class AnalyzedPostRepository:
    """Repository abstraction for `AnalyzedPost` operations.

    This class provides a clean interface for persisting and retrieving
    analytics data, abstracting away SQLAlchemy details from the orchestrator.
    """

    def __init__(self, db: PostgresDatabase, logger: Optional[Logger] = None) -> None:
        """Initialize repository with database instance.

        Args:
            db: PostgresDatabase instance
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
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
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
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
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
        """Sanitize analytics data."""
        sanitized = analytics_data.copy()

        for key, value in sanitized.items():
            if isinstance(value, str) and value.upper() == NULL_STRING:
                sanitized[key] = None

        if "id" in sanitized and sanitized["id"] is not None:
            sanitized["id"] = str(sanitized["id"])

        datetime_fields = [
            "published_at",
            "analyzed_at",
            "crawled_at",
            "created_at",
            "updated_at",
        ]
        for field in datetime_fields:
            if field in sanitized and isinstance(sanitized[field], str):
                try:
                    sanitized[field] = datetime.fromisoformat(
                        sanitized[field].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    sanitized[field] = None

        return sanitized

    async def save(self, analytics_data: Dict[str, Any]) -> AnalyzedPost:
        """Save analytics result into the `analyzed_posts` table.

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
            async with self.db.get_session() as session:
                # Check if exists
                stmt = select(AnalyzedPost).where(AnalyzedPost.id == post_id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is None:
                    post = AnalyzedPost(**analytics_data)
                    session.add(post)
                    if self.logger:
                        self.logger.debug(
                            f"Creating new AnalyzedPost record: id={post_id}"
                        )
                else:
                    post = existing
                    for key, value in analytics_data.items():
                        if hasattr(post, key):
                            setattr(post, key, value)
                    if self.logger:
                        self.logger.debug(
                            f"Updating existing AnalyzedPost record: id={post_id}"
                        )

                await session.commit()
                await session.refresh(post)
                return post

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(
                    f"Database error saving analytics for post_id={post_id}: {exc}"
                )
            raise AnalyzedPostRepositoryError(
                f"Failed to save analytics: {exc}"
            ) from exc


__all__ = ["AnalyzedPostRepository", "AnalyzedPostRepositoryError"]

"""Repository for persisting analytics results to the database."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.database import PostAnalytics


class AnalyticsRepository:
    """Repository abstraction for `PostAnalytics` operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, analytics_data: Dict[str, Any]) -> PostAnalytics:
        """Save analytics result into the `post_analytics` table.

        This method performs an insert-or-update (upsert-like) behavior based on
        the primary key `id`, so re-processing the same post overwrites the
        previous analytics record.
        """
        post_id = analytics_data.get("id")
        existing = None
        if post_id is not None:
            existing = self.get_by_id(post_id)

        if existing is None:
            post = PostAnalytics(**analytics_data)
            self.db.add(post)
        else:
            post = existing
            for key, value in analytics_data.items():
                setattr(post, key, value)

        self.db.commit()
        self.db.refresh(post)
        return post

    def get_by_id(self, post_id: str) -> Optional[PostAnalytics]:
        """Fetch a `PostAnalytics` record by its primary key."""
        return self.db.query(PostAnalytics).filter(PostAnalytics.id == post_id).one_or_none()

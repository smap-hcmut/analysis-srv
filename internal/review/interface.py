"""review/interface.py — IReviewRepository ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from internal.review.type import ReviewItem, ReviewDecision, ReviewQueueSummary


class IReviewRepository(ABC):
    """Persistence contract for the review queue.

    Implementations may use PostgreSQL (production) or an in-memory
    dict store (tests / local dev).
    """

    @abstractmethod
    def save(self, item: "ReviewItem") -> None:
        """Persist a new (or updated) ReviewItem."""

    @abstractmethod
    def get_by_id(self, item_id: str) -> "ReviewItem | None":
        """Return the ReviewItem with *item_id*, or None if not found."""

    @abstractmethod
    def get_pending(self, project_id: str, limit: int = 100) -> "list[ReviewItem]":
        """Return up to *limit* pending items for *project_id*, oldest first."""

    @abstractmethod
    def count_pending(self, project_id: str) -> int:
        """Return the number of pending items for *project_id*."""

    @abstractmethod
    def get_summary(self, project_id: str) -> "ReviewQueueSummary":
        """Return aggregate status counts for *project_id*."""


__all__ = ["IReviewRepository"]

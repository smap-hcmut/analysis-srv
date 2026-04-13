"""review/usecase/usecase.py — ReviewUseCase: orchestrates all review operations."""

from __future__ import annotations

from internal.review.constant import DEFAULT_FETCH_LIMIT, LOW_CONFIDENCE_THRESHOLD
from internal.review.interface import IReviewRepository
from internal.review.type import ReviewDecision, ReviewItem, ReviewQueueSummary
from internal.review.usecase.enqueue_item import enqueue_review_item
from internal.review.usecase.get_pending_items import get_pending_items
from internal.review.usecase.resolve_item import resolve_review_item


class ReviewUseCase:
    """High-level API over the review queue.

    Wraps individual usecase functions behind a single injectable object
    so that callers (pipeline stages, API handlers) can swap the backing
    repository without touching business logic.
    """

    def __init__(self, repo: IReviewRepository) -> None:
        self._repo = repo

    def enqueue(
        self,
        run_id: str,
        project_id: str,
        mention_id: str,
        fact_type: str,
        fact_payload: dict,
        confidence: float,
        *,
        confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
        force: bool = False,
    ) -> ReviewItem | None:
        """Enqueue a fact for review if it meets the confidence threshold."""
        return enqueue_review_item(
            self._repo,
            run_id=run_id,
            project_id=project_id,
            mention_id=mention_id,
            fact_type=fact_type,
            fact_payload=fact_payload,
            confidence=confidence,
            confidence_threshold=confidence_threshold,
            force=force,
        )

    def get_pending(
        self,
        project_id: str,
        limit: int = DEFAULT_FETCH_LIMIT,
    ) -> list[ReviewItem]:
        """Return pending items for *project_id*."""
        return get_pending_items(self._repo, project_id=project_id, limit=limit)

    def resolve(
        self,
        item_id: str,
        decision: ReviewDecision,
        *,
        note: str | None = None,
    ) -> ReviewItem:
        """Apply *decision* to the ReviewItem identified by *item_id*."""
        return resolve_review_item(
            self._repo, item_id=item_id, decision=decision, note=note
        )

    def summary(self, project_id: str) -> ReviewQueueSummary:
        """Return aggregate counts for *project_id*."""
        return self._repo.get_summary(project_id)


__all__ = ["ReviewUseCase"]

"""review/usecase/enqueue_item.py — enqueue a low-confidence enrichment fact."""

from __future__ import annotations

from internal.review.constant import (
    LOW_CONFIDENCE_THRESHOLD,
    MAX_QUEUE_SIZE,
    REVIEWABLE_FACT_TYPES,
)
from internal.review.errors import ReviewQueueFullError
from internal.review.interface import IReviewRepository
from internal.review.type import ReviewItem


def enqueue_review_item(
    repo: IReviewRepository,
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
    """Enqueue *fact_payload* for human review if conditions are met.

    An item is queued when **all** of the following hold:
    - ``fact_type`` is in ``REVIEWABLE_FACT_TYPES``
    - ``confidence < confidence_threshold`` (or *force* is True)
    - The pending queue for *project_id* has not reached ``MAX_QUEUE_SIZE``

    Returns the created :class:`ReviewItem`, or ``None`` if the fact
    does not qualify for review (skipped silently — not an error).

    Raises :class:`ReviewQueueFullError` if the queue is at capacity.
    """
    if not force:
        if fact_type not in REVIEWABLE_FACT_TYPES:
            return None
        if confidence >= confidence_threshold:
            return None

    pending_count = repo.count_pending(project_id)
    if pending_count >= MAX_QUEUE_SIZE:
        raise ReviewQueueFullError(
            f"Review queue for project '{project_id}' is full "
            f"({pending_count}/{MAX_QUEUE_SIZE} pending items). "
            "Resolve existing items before enqueueing more."
        )

    item = ReviewItem.new(
        run_id=run_id,
        project_id=project_id,
        mention_id=mention_id,
        fact_type=fact_type,
        fact_payload=fact_payload,
        confidence=confidence,
    )
    repo.save(item)
    return item


__all__ = ["enqueue_review_item"]

"""review/usecase/get_pending_items.py — fetch pending review items."""

from __future__ import annotations

from internal.review.constant import DEFAULT_FETCH_LIMIT
from internal.review.interface import IReviewRepository
from internal.review.type import ReviewItem


def get_pending_items(
    repo: IReviewRepository,
    project_id: str,
    limit: int = DEFAULT_FETCH_LIMIT,
) -> list[ReviewItem]:
    """Return up to *limit* pending ReviewItems for *project_id*, oldest first.

    Returns an empty list if the queue is empty — never raises.
    """
    return repo.get_pending(project_id=project_id, limit=limit)


__all__ = ["get_pending_items"]

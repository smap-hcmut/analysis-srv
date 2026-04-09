"""review/usecase/resolve_item.py — apply a reviewer decision to a ReviewItem."""

from __future__ import annotations

from datetime import datetime, timezone

from internal.review.errors import (
    ReviewItemAlreadyResolvedError,
    ReviewItemNotFoundError,
)
from internal.review.interface import IReviewRepository
from internal.review.type import ReviewDecision, ReviewItem

_DECISION_TO_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "skip": "skipped",
}


def resolve_review_item(
    repo: IReviewRepository,
    item_id: str,
    decision: ReviewDecision,
    *,
    note: str | None = None,
) -> ReviewItem:
    """Apply *decision* to the ReviewItem identified by *item_id*.

    Parameters
    ----------
    repo     : Repository to read from / write to.
    item_id  : UUID string of the ReviewItem.
    decision : One of ``"approve"``, ``"reject"``, ``"skip"``.
    note     : Optional reviewer note stored on the item.

    Returns the updated ReviewItem.

    Raises
    ------
    ReviewItemNotFoundError        : If no item with *item_id* exists.
    ReviewItemAlreadyResolvedError : If the item is already resolved.
    """
    item = repo.get_by_id(item_id)
    if item is None:
        raise ReviewItemNotFoundError(f"ReviewItem '{item_id}' not found.")
    if item.is_resolved():
        raise ReviewItemAlreadyResolvedError(
            f"ReviewItem '{item_id}' is already '{item.status}' — "
            "cannot apply a second decision."
        )

    item.status = _DECISION_TO_STATUS[decision]  # type: ignore[assignment]
    item.resolved_at = datetime.now(timezone.utc)
    item.resolution_note = note
    repo.save(item)
    return item


__all__ = ["resolve_review_item"]

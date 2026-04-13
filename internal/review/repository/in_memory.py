"""review/repository/in_memory.py — in-memory repository for local/test use."""

from __future__ import annotations

from internal.review.interface import IReviewRepository
from internal.review.type import ReviewItem, ReviewQueueSummary


class InMemoryReviewRepository(IReviewRepository):
    """Thread-unsafe in-memory repository — suitable for tests and local dev."""

    def __init__(self) -> None:
        self._store: dict[str, ReviewItem] = {}

    def save(self, item: ReviewItem) -> None:
        self._store[item.id] = item

    def get_by_id(self, item_id: str) -> ReviewItem | None:
        return self._store.get(item_id)

    def get_pending(self, project_id: str, limit: int = 100) -> list[ReviewItem]:
        items = [
            i
            for i in self._store.values()
            if i.project_id == project_id and i.status == "pending"
        ]
        # oldest first (stable sort by created_at)
        items.sort(key=lambda i: i.created_at)
        return items[:limit]

    def count_pending(self, project_id: str) -> int:
        return sum(
            1
            for i in self._store.values()
            if i.project_id == project_id and i.status == "pending"
        )

    def get_summary(self, project_id: str) -> ReviewQueueSummary:
        items = [i for i in self._store.values() if i.project_id == project_id]
        summary = ReviewQueueSummary(project_id=project_id, total=len(items))
        for item in items:
            if item.status == "pending":
                summary.pending += 1
            elif item.status == "approved":
                summary.approved += 1
            elif item.status == "rejected":
                summary.rejected += 1
            elif item.status == "skipped":
                summary.skipped += 1
        return summary


__all__ = ["InMemoryReviewRepository"]

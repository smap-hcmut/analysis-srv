"""review/usecase/new.py — factory for ReviewUseCase."""

from __future__ import annotations

from internal.review.interface import IReviewRepository
from internal.review.repository.in_memory import InMemoryReviewRepository
from internal.review.usecase.usecase import ReviewUseCase


def new_review_usecase(
    repo: IReviewRepository | None = None,
) -> ReviewUseCase:
    """Return a ReviewUseCase backed by *repo* (default: InMemoryReviewRepository)."""
    if repo is None:
        repo = InMemoryReviewRepository()
    return ReviewUseCase(repo)


__all__ = ["new_review_usecase"]

"""review/errors.py — review module exceptions."""

from __future__ import annotations


class ReviewError(Exception):
    """Base class for review errors."""


class ReviewItemNotFoundError(ReviewError):
    """Raised when a ReviewItem with the given ID does not exist."""


class ReviewItemAlreadyResolvedError(ReviewError):
    """Raised when attempting to resolve an already-resolved ReviewItem."""


class ReviewQueueFullError(ReviewError):
    """Raised when the queue has reached MAX_QUEUE_SIZE for the project."""


__all__ = [
    "ReviewError",
    "ReviewItemNotFoundError",
    "ReviewItemAlreadyResolvedError",
    "ReviewQueueFullError",
]

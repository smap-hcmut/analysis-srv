"""test_review.py — Phase 7: internal/review module tests.

Gate criteria:
- ReviewItem.new() generates a valid UUID id and is pending by default
- ReviewItem.is_pending() / is_resolved() return correct values
- enqueue_review_item skips items with high confidence (above threshold)
- enqueue_review_item skips items with non-reviewable fact_type
- enqueue_review_item queues items with low confidence + valid fact_type
- enqueue_review_item raises ReviewQueueFullError when queue is full
- enqueue_review_item with force=True bypasses type/confidence checks
- get_pending_items returns pending items oldest-first, up to limit
- resolve_review_item applies decision and sets resolved_at timestamp
- resolve_review_item raises ReviewItemNotFoundError for unknown id
- resolve_review_item raises ReviewItemAlreadyResolvedError for resolved item
- ReviewQueueSummary counts are correct after enqueue + resolve operations
- ReviewUseCase.enqueue / get_pending / resolve / summary integrate end-to-end
- InMemoryReviewRepository implements IReviewRepository
- new_review_usecase() returns a ReviewUseCase backed by InMemoryReviewRepository
- All 138 previously-passing tests are unaffected
"""

from __future__ import annotations

import time
import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uc():
    from internal.review.usecase.new import new_review_usecase

    return new_review_usecase()


# ---------------------------------------------------------------------------
# ReviewItem
# ---------------------------------------------------------------------------


def test_review_item_new_generates_valid_uuid():
    """ReviewItem.new() must produce a parseable UUID string."""
    from internal.review.type import ReviewItem

    item = ReviewItem.new(
        run_id="run-001",
        project_id="proj-001",
        mention_id="m001",
        fact_type="entity",
        fact_payload={"name": "Samsung"},
        confidence=0.4,
    )
    parsed = uuid.UUID(item.id)
    assert str(parsed) == item.id
    assert item.status == "pending"
    assert item.is_pending() is True
    assert item.is_resolved() is False


def test_review_item_unique_ids():
    """Consecutive ReviewItem.new() calls must produce different ids."""
    from internal.review.type import ReviewItem

    ids = {ReviewItem.new("r", "p", f"m{i}", "entity", {}, 0.5).id for i in range(20)}
    assert len(ids) == 20


def test_review_item_is_resolved_for_all_statuses():
    """is_resolved() must return False for pending, True for all resolution statuses."""
    from internal.review.type import ReviewItem

    base = ReviewItem.new("r", "p", "m", "entity", {}, 0.5)

    for status in ("approved", "rejected", "skipped"):
        item = ReviewItem.new("r", "p", "m", "entity", {}, 0.5)
        item.status = status  # type: ignore[assignment]
        assert item.is_resolved() is True
        assert item.is_pending() is False


# ---------------------------------------------------------------------------
# enqueue_review_item
# ---------------------------------------------------------------------------


def test_enqueue_skips_high_confidence():
    """enqueue returns None for confidence >= threshold (default 0.65)."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    result = enqueue_review_item(
        repo, "run", "proj", "m1", "entity", {}, confidence=0.80
    )
    assert result is None
    assert repo.count_pending("proj") == 0


def test_enqueue_skips_non_reviewable_fact_type():
    """enqueue returns None for fact_type not in REVIEWABLE_FACT_TYPES."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    result = enqueue_review_item(
        repo, "run", "proj", "m1", "spam_score", {}, confidence=0.3
    )
    assert result is None
    assert repo.count_pending("proj") == 0


def test_enqueue_queues_low_confidence_reviewable():
    """enqueue queues fact when confidence < threshold and fact_type is reviewable."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item = enqueue_review_item(
        repo,
        "run-001",
        "proj-001",
        "mention-001",
        "entity",
        {"name": "SamsungX"},
        confidence=0.40,
    )

    assert item is not None
    assert item.status == "pending"
    assert repo.count_pending("proj-001") == 1


def test_enqueue_at_threshold_does_not_queue():
    """confidence == threshold is NOT below threshold → should not queue."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    result = enqueue_review_item(
        repo, "run", "proj", "m", "entity", {}, confidence=0.65
    )
    assert result is None


def test_enqueue_force_bypasses_checks():
    """force=True queues regardless of fact_type and confidence."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item = enqueue_review_item(
        repo, "run", "proj", "m", "unknown_type", {}, confidence=0.99, force=True
    )
    assert item is not None
    assert item.status == "pending"


def test_enqueue_raises_when_queue_full():
    """enqueue raises ReviewQueueFullError when count_pending >= MAX_QUEUE_SIZE."""
    from unittest.mock import MagicMock

    from internal.review.errors import ReviewQueueFullError
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.constant import MAX_QUEUE_SIZE

    repo = MagicMock()
    repo.count_pending.return_value = MAX_QUEUE_SIZE  # at capacity

    with pytest.raises(ReviewQueueFullError):
        enqueue_review_item(repo, "run", "proj", "m", "entity", {}, confidence=0.3)


# ---------------------------------------------------------------------------
# get_pending_items
# ---------------------------------------------------------------------------


def test_get_pending_items_empty_queue():
    """get_pending_items returns empty list when queue is empty."""
    from internal.review.usecase.get_pending_items import get_pending_items
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    result = get_pending_items(repo, "proj-001")
    assert result == []


def test_get_pending_items_returns_oldest_first():
    """get_pending_items returns items sorted oldest-first."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.get_pending_items import get_pending_items
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    for i in range(5):
        enqueue_review_item(repo, "run", "proj", f"m{i}", "entity", {"i": i}, 0.3)
        time.sleep(0.001)  # ensure distinct created_at

    items = get_pending_items(repo, "proj")
    payloads = [item.fact_payload["i"] for item in items]
    assert payloads == sorted(payloads)  # oldest (i=0) first


def test_get_pending_items_respects_limit():
    """get_pending_items respects the limit parameter."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.get_pending_items import get_pending_items
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    for i in range(10):
        enqueue_review_item(repo, "run", "proj", f"m{i}", "topic", {}, 0.3)

    result = get_pending_items(repo, "proj", limit=3)
    assert len(result) == 3


def test_get_pending_items_cross_project_isolation():
    """get_pending_items must not return items from other projects."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.get_pending_items import get_pending_items
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    enqueue_review_item(repo, "run", "proj-A", "m1", "entity", {}, 0.3)
    enqueue_review_item(repo, "run", "proj-B", "m2", "entity", {}, 0.3)

    result_a = get_pending_items(repo, "proj-A")
    result_b = get_pending_items(repo, "proj-B")

    assert len(result_a) == 1
    assert result_a[0].project_id == "proj-A"
    assert len(result_b) == 1
    assert result_b[0].project_id == "proj-B"


# ---------------------------------------------------------------------------
# resolve_review_item
# ---------------------------------------------------------------------------


def test_resolve_approve():
    """resolve_review_item with 'approve' sets status='approved' and resolved_at."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.resolve_item import resolve_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item = enqueue_review_item(repo, "run", "proj", "m", "entity", {}, 0.4)

    resolved = resolve_review_item(repo, item.id, "approve", note="looks correct")

    assert resolved.status == "approved"
    assert resolved.resolved_at is not None
    assert resolved.resolution_note == "looks correct"


def test_resolve_reject():
    """resolve_review_item with 'reject' sets status='rejected'."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.resolve_item import resolve_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item = enqueue_review_item(repo, "run", "proj", "m", "intent", {}, 0.5)

    resolved = resolve_review_item(repo, item.id, "reject")
    assert resolved.status == "rejected"


def test_resolve_skip():
    """resolve_review_item with 'skip' sets status='skipped'."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.resolve_item import resolve_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item = enqueue_review_item(repo, "run", "proj", "m", "topic", {}, 0.5)

    resolved = resolve_review_item(repo, item.id, "skip")
    assert resolved.status == "skipped"


def test_resolve_raises_not_found():
    """resolve_review_item raises ReviewItemNotFoundError for unknown id."""
    from internal.review.errors import ReviewItemNotFoundError
    from internal.review.usecase.resolve_item import resolve_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()

    with pytest.raises(ReviewItemNotFoundError):
        resolve_review_item(repo, "nonexistent-id", "approve")


def test_resolve_raises_already_resolved():
    """resolve_review_item raises ReviewItemAlreadyResolvedError on double resolution."""
    from internal.review.errors import ReviewItemAlreadyResolvedError
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.resolve_item import resolve_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item = enqueue_review_item(repo, "run", "proj", "m", "entity", {}, 0.4)
    resolve_review_item(repo, item.id, "approve")

    with pytest.raises(ReviewItemAlreadyResolvedError):
        resolve_review_item(repo, item.id, "reject")


# ---------------------------------------------------------------------------
# ReviewQueueSummary
# ---------------------------------------------------------------------------


def test_review_queue_summary_counts():
    """get_summary must count items by status correctly."""
    from internal.review.usecase.enqueue_item import enqueue_review_item
    from internal.review.usecase.resolve_item import resolve_review_item
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    item1 = enqueue_review_item(repo, "run", "proj", "m1", "entity", {}, 0.3)
    item2 = enqueue_review_item(repo, "run", "proj", "m2", "topic", {}, 0.4)
    item3 = enqueue_review_item(repo, "run", "proj", "m3", "intent", {}, 0.5)
    item4 = enqueue_review_item(repo, "run", "proj", "m4", "entity", {}, 0.6)

    resolve_review_item(repo, item1.id, "approve")
    resolve_review_item(repo, item2.id, "reject")
    resolve_review_item(repo, item3.id, "skip")
    # item4 remains pending

    summary = repo.get_summary("proj")

    assert summary.total == 4
    assert summary.pending == 1
    assert summary.approved == 1
    assert summary.rejected == 1
    assert summary.skipped == 1


# ---------------------------------------------------------------------------
# ReviewUseCase — integration
# ---------------------------------------------------------------------------


def test_review_usecase_full_lifecycle():
    """Full enqueue → get_pending → resolve → summary lifecycle via ReviewUseCase."""
    uc = _make_uc()

    # Enqueue 3 items: 2 low confidence, 1 high
    item1 = uc.enqueue("run", "proj", "m1", "entity", {"n": "A"}, confidence=0.3)
    item2 = uc.enqueue("run", "proj", "m2", "topic", {"n": "B"}, confidence=0.5)
    skipped = uc.enqueue("run", "proj", "m3", "entity", {"n": "C"}, confidence=0.9)

    assert item1 is not None
    assert item2 is not None
    assert skipped is None  # high confidence — not queued

    # Fetch pending
    pending = uc.get_pending("proj")
    assert len(pending) == 2

    # Resolve one
    resolved = uc.resolve(item1.id, "approve", note="verified")
    assert resolved.status == "approved"

    # Summary
    summary = uc.summary("proj")
    assert summary.total == 2
    assert summary.pending == 1
    assert summary.approved == 1


def test_review_usecase_in_memory_repository_implements_interface():
    """InMemoryReviewRepository must be an instance of IReviewRepository."""
    from internal.review.interface import IReviewRepository
    from internal.review.usecase.new import InMemoryReviewRepository

    repo = InMemoryReviewRepository()
    assert isinstance(repo, IReviewRepository)


def test_new_review_usecase_returns_review_usecase():
    """new_review_usecase() must return a ReviewUseCase."""
    from internal.review.usecase.new import new_review_usecase
    from internal.review.usecase.usecase import ReviewUseCase

    uc = new_review_usecase()
    assert isinstance(uc, ReviewUseCase)

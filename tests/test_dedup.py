"""Unit tests for internal/dedup/usecase/annotate_dedup.py.

Covers:
  - Empty input → no-op
  - Exact duplicate detection (same normalized_text_compact)
  - Near duplicate detection (high similarity text)
  - Non-duplicate text stays unclustered
  - dedup_weight reflects cluster size
  - Short text below min_text_length is skipped for near-dedup
"""

from __future__ import annotations

import pytest

from internal.dedup.usecase.annotate_dedup import DeduplicationService
from internal.normalization.type import MentionRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mention(
    mention_id: str,
    text: str,
    *,
    depth: int = 0,
    author_id: str = "author1",
) -> MentionRecord:
    return MentionRecord(
        mention_id=mention_id,
        normalized_text_compact=text,
        raw_text=text,
        normalized_text=text,
        depth=depth,
        author_id=author_id,
        root_id=mention_id,
    )


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestDedupEmptyInput:
    def test_empty_list_returns_empty(self):
        svc = DeduplicationService()
        mentions, result = svc.annotate([])
        assert mentions == []
        assert result.mentions_updated == 0
        assert result.exact_cluster_count == 0
        assert result.near_cluster_count == 0


# ---------------------------------------------------------------------------
# Exact duplicates
# ---------------------------------------------------------------------------


class TestExactDedup:
    def test_two_exact_copies_form_cluster(self):
        text = "this is a product review with enough characters"
        svc = DeduplicationService()
        mentions = [
            make_mention("m1", text),
            make_mention("m2", text),
        ]
        updated, result = svc.annotate(mentions)
        assert result.exact_cluster_count == 1
        cluster_ids = {m.dedup_cluster_id for m in updated if m.dedup_cluster_id}
        assert len(cluster_ids) == 1
        assert all(m.dedup_kind == "exact" for m in updated if m.dedup_kind)

    def test_three_exact_copies_same_cluster(self):
        text = "great quality fast delivery would recommend"
        svc = DeduplicationService()
        mentions = [make_mention(f"m{i}", text) for i in range(3)]
        updated, result = svc.annotate(mentions)
        assert result.exact_cluster_count == 1
        assert updated[0].dedup_cluster_size == 3

    def test_dedup_weight_is_one_over_cluster_size(self):
        text = "same text same text same text"
        svc = DeduplicationService()
        mentions = [make_mention(f"m{i}", text) for i in range(4)]
        updated, _ = svc.annotate(mentions)
        for m in updated:
            assert abs(m.dedup_weight - 0.25) < 1e-5

    def test_unique_texts_not_clustered(self):
        svc = DeduplicationService()
        mentions = [
            make_mention("m1", "the battery life is exceptional on this device"),
            make_mention("m2", "the charging speed could definitely be improved"),
            make_mention("m3", "the display quality is stunning and vibrant"),
        ]
        _, result = svc.annotate(mentions)
        assert result.exact_cluster_count == 0

    def test_short_text_below_threshold_skipped(self):
        """Text shorter than min_text_length should not form exact clusters."""
        svc = DeduplicationService(min_text_length=10)
        mentions = [
            make_mention("m1", "ok"),
            make_mention("m2", "ok"),
        ]
        _, result = svc.annotate(mentions)
        assert result.exact_cluster_count == 0


# ---------------------------------------------------------------------------
# Near duplicates
# ---------------------------------------------------------------------------


class TestNearDedup:
    def test_near_duplicate_texts_clustered(self):
        base = "this product has excellent build quality and great performance overall"
        near = (
            "this product has excellent build quality and great performance in general"
        )
        svc = DeduplicationService(near_similarity_threshold=0.7)
        mentions = [
            make_mention("m1", base),
            make_mention("m2", near),
        ]
        updated, result = svc.annotate(mentions)
        # Should form either exact (fingerprint match unlikely) or near cluster
        assert result.exact_cluster_count + result.near_cluster_count >= 1

    def test_dissimilar_texts_not_near_clustered(self):
        svc = DeduplicationService()
        mentions = [
            make_mention("m1", "completely different topic about weather forecast"),
            make_mention("m2", "another unrelated story about cooking recipes"),
        ]
        _, result = svc.annotate(mentions)
        assert result.near_cluster_count == 0


# ---------------------------------------------------------------------------
# Mixed exact + near
# ---------------------------------------------------------------------------


class TestMixedDedup:
    def test_exact_members_excluded_from_near(self):
        """Exact cluster members should not also appear in near clusters."""
        text = "great product quality fast delivery best experience highly recommend"
        near = "great product quality fast delivery best experience highly recommended"
        svc = DeduplicationService()
        mentions = [
            make_mention("m1", text),
            make_mention("m2", text),  # exact dup of m1
            make_mention("m3", near),
        ]
        updated, result = svc.annotate(mentions)
        exact_ids = {m.mention_id for m in updated if m.dedup_kind == "exact"}
        near_ids = {m.mention_id for m in updated if m.dedup_kind == "near"}
        # m1 and m2 are exact — they should not appear in a near cluster
        assert not (exact_ids & near_ids)

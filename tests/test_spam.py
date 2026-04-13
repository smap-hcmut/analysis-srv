"""Unit tests for internal/spam/usecase/score_authors.py.

Covers:
  - Empty input
  - Clean mentions → low spam score
  - Repost-like text → high mention spam score
  - Bursty author → elevated author inorganic score
  - Duplicate cluster participation elevates score
  - quality_weight discounted for suspicious mentions
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from internal.normalization.type import MentionRecord
from internal.spam.usecase.score_authors import SpamScoringService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_BASE_TIME = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_mention(
    mention_id: str,
    text: str,
    *,
    author_id: str = "author1",
    depth: int = 0,
    posted_at: datetime | None = None,
    dedup_cluster_size: int = 1,
    dedup_weight: float = 1.0,
    urls: list[str] | None = None,
    text_quality_flags: list[str] | None = None,
) -> MentionRecord:
    return MentionRecord(
        mention_id=mention_id,
        author_id=author_id,
        normalized_text_compact=text,
        normalized_text=text,
        raw_text=text,
        depth=depth,
        root_id=mention_id,
        posted_at=posted_at or _BASE_TIME,
        dedup_cluster_size=dedup_cluster_size,
        dedup_weight=dedup_weight,
        urls=urls or [],
        text_quality_flags=text_quality_flags or [],
    )


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestSpamEmptyInput:
    def test_empty_list_returns_empty(self):
        svc = SpamScoringService()
        mentions, result = svc.annotate([])
        assert mentions == []
        assert result.mentions_updated == 0
        assert result.author_profiles == []


# ---------------------------------------------------------------------------
# Low-spam mentions
# ---------------------------------------------------------------------------


class TestLowSpamMentions:
    def test_clean_diverse_text_low_score(self):
        svc = SpamScoringService()
        mentions = [
            make_mention(
                "m1", "battery life excellent two days full charge impressive"
            ),
            make_mention(
                "m2", "display colour accuracy vivid sharp contrast superb quality"
            ),
        ]
        updated, _ = svc.annotate(mentions)
        for m in updated:
            assert m.mention_spam_score < 0.5

    def test_clean_mention_not_suspicious(self):
        svc = SpamScoringService()
        mentions = [make_mention("m1", "great phone outstanding camera performance")]
        updated, _ = svc.annotate(mentions)
        assert updated[0].mention_suspicious is False
        assert updated[0].author_suspicious is False


# ---------------------------------------------------------------------------
# Repost-like text
# ---------------------------------------------------------------------------


class TestRepostLike:
    def test_rt_prefix_raises_score(self):
        svc = SpamScoringService()
        mentions = [make_mention("m1", "rt this product is amazing quality")]
        updated, _ = svc.annotate(mentions)
        assert updated[0].mention_spam_score > 0.0

    def test_repost_prefix_raises_score(self):
        svc = SpamScoringService()
        mentions = [make_mention("m1", "repost great value for money product")]
        updated, _ = svc.annotate(mentions)
        assert updated[0].mention_spam_score > 0.0


# ---------------------------------------------------------------------------
# Duplicate cluster participation
# ---------------------------------------------------------------------------


class TestDuplicateClusterPressure:
    def test_large_cluster_raises_spam_score(self):
        svc = SpamScoringService()
        # dedup_cluster_size=10 → high duplicate_pressure
        mentions = [
            make_mention(
                "m1",
                "copy paste review text",
                dedup_cluster_size=10,
                dedup_weight=0.1,
            )
        ]
        updated, _ = svc.annotate(mentions)
        assert updated[0].mention_spam_score > 0.1


# ---------------------------------------------------------------------------
# Author burstiness
# ---------------------------------------------------------------------------


class TestAuthorBurstiness:
    def test_bursty_author_high_inorganic_score(self):
        """10 mentions in 5 minutes → high burstiness."""
        svc = SpamScoringService(burst_window_minutes=60)
        base = _BASE_TIME
        mentions = [
            make_mention(
                f"m{i}",
                f"review number {i} product quality excellent value",
                author_id="spammer",
                posted_at=base + timedelta(seconds=i * 30),
            )
            for i in range(10)
        ]
        _, result = svc.annotate(mentions)
        profile = result.author_profiles[0]
        assert profile.burstiness_score > 0.5

    def test_spread_out_author_low_burstiness(self):
        """One mention per day → burstiness near zero."""
        svc = SpamScoringService()
        base = _BASE_TIME
        mentions = [
            make_mention(
                f"m{i}",
                f"different review text number {i} unique content",
                author_id="genuine",
                posted_at=base + timedelta(days=i),
            )
            for i in range(5)
        ]
        _, result = svc.annotate(mentions)
        profile = result.author_profiles[0]
        assert profile.burstiness_score < 0.5


# ---------------------------------------------------------------------------
# quality_weight
# ---------------------------------------------------------------------------


class TestQualityWeight:
    def test_clean_mention_quality_weight_near_one(self):
        svc = SpamScoringService()
        mentions = [
            make_mention(
                "m1", "high quality product strong build excellent performance"
            )
        ]
        updated, _ = svc.annotate(mentions)
        assert updated[0].quality_weight > 0.7

    def test_suspicious_mention_quality_weight_discounted(self):
        svc = SpamScoringService(mention_threshold=0.01)
        # Force mention_spam_score to be high via duplicate cluster
        mentions = [
            make_mention(
                "m1",
                "rt product amazing quality value",
                dedup_cluster_size=20,
                dedup_weight=0.05,
            )
        ]
        updated, _ = svc.annotate(mentions)
        # quality_weight should be less than dedup_weight=0.05 * 1.0
        assert updated[0].quality_weight <= 0.05


# ---------------------------------------------------------------------------
# text_quality_flags updated by spam stage
# ---------------------------------------------------------------------------


class TestSpamQualityFlags:
    def test_suspicious_mention_adds_spam_like_flag(self):
        svc = SpamScoringService(mention_threshold=0.01)
        mentions = [
            make_mention(
                "m1",
                "rt copy paste spam text",
                dedup_cluster_size=20,
                dedup_weight=0.05,
            )
        ]
        updated, _ = svc.annotate(mentions)
        assert "spam_like" in updated[0].text_quality_flags

    def test_duplicate_cluster_adds_duplicate_like_flag(self):
        svc = SpamScoringService()
        mentions = [
            make_mention(
                "m1",
                "product review text quality",
                dedup_cluster_size=3,
                dedup_weight=0.333,
            )
        ]
        updated, _ = svc.annotate(mentions)
        assert "duplicate_like" in updated[0].text_quality_flags

"""Unit tests for internal/threads/usecase/build_threads.py.

Covers:
  - Empty input
  - Flat list (all posts at depth=0)
  - Post + comments thread structure
  - Deep reply chain (depth >= 2)
  - Multi-root threads
  - Lineage / sibling / child relationships in MentionContext
  - ThreadSummary counts
"""

from __future__ import annotations

import pytest

from internal.normalization.type import MentionRecord
from internal.threads.usecase.build_threads import build_threads
from internal.threads.type import ThreadBundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mention(
    mention_id: str,
    text: str,
    *,
    root_id: str,
    parent_id: str | None = None,
    depth: int = 0,
    author_id: str = "author1",
    sort_score: float | None = None,
) -> MentionRecord:
    return MentionRecord(
        mention_id=mention_id,
        raw_text=text,
        normalized_text=text,
        normalized_text_compact=text,
        root_id=root_id,
        parent_id=parent_id,
        depth=depth,
        author_id=author_id,
        sort_score=sort_score,
    )


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestThreadsEmptyInput:
    def test_empty_returns_empty_bundle(self):
        bundle = build_threads([])
        assert bundle.summaries == []
        assert bundle.edges == []
        assert bundle.contexts == []


# ---------------------------------------------------------------------------
# Single post (no comments)
# ---------------------------------------------------------------------------


class TestSinglePost:
    def test_single_post_one_summary(self):
        mentions = [make_mention("post1", "root post text", root_id="post1")]
        bundle = build_threads(mentions)
        assert len(bundle.summaries) == 1
        summary = bundle.summaries[0]
        assert summary.root_id == "post1"
        assert summary.total_mentions == 1
        assert summary.comment_count == 0
        assert summary.reply_count == 0

    def test_single_post_no_edges(self):
        mentions = [make_mention("post1", "root post text", root_id="post1")]
        bundle = build_threads(mentions)
        assert bundle.edges == []

    def test_single_post_one_context(self):
        mentions = [make_mention("post1", "root post text", root_id="post1")]
        bundle = build_threads(mentions)
        assert len(bundle.contexts) == 1
        ctx = bundle.contexts[0]
        assert ctx.mention_id == "post1"
        assert ctx.parent_id is None
        assert ctx.lineage_ids == []


# ---------------------------------------------------------------------------
# Post + direct comments (depth=1)
# ---------------------------------------------------------------------------


class TestPostWithComments:
    def _build(self):
        mentions = [
            make_mention("post1", "root post content", root_id="post1"),
            make_mention(
                "comment1",
                "first comment text",
                root_id="post1",
                parent_id="post1",
                depth=1,
                sort_score=10.0,
            ),
            make_mention(
                "comment2",
                "second comment text",
                root_id="post1",
                parent_id="post1",
                depth=1,
                sort_score=5.0,
            ),
        ]
        return build_threads(mentions)

    def test_summary_comment_count(self):
        bundle = self._build()
        summary = bundle.summaries[0]
        assert summary.comment_count == 2

    def test_summary_reply_count_zero(self):
        bundle = self._build()
        summary = bundle.summaries[0]
        assert summary.reply_count == 0

    def test_summary_total_descendants(self):
        bundle = self._build()
        summary = bundle.summaries[0]
        assert summary.total_descendants == 2

    def test_top_comment_sorted_by_score(self):
        bundle = self._build()
        summary = bundle.summaries[0]
        assert summary.top_comment_ids[0] == "comment1"

    def test_edges_created_for_comments(self):
        bundle = self._build()
        assert len(bundle.edges) == 2
        for edge in bundle.edges:
            assert edge.root_id == "post1"
            assert edge.parent_id == "post1"
            assert edge.depth == 1

    def test_comment_context_has_parent_text(self):
        bundle = self._build()
        ctx_map = {c.mention_id: c for c in bundle.contexts}
        assert ctx_map["comment1"].parent_text == "root post content"
        assert ctx_map["comment1"].root_text == "root post content"

    def test_sibling_ids_populated(self):
        bundle = self._build()
        ctx_map = {c.mention_id: c for c in bundle.contexts}
        assert "comment2" in ctx_map["comment1"].sibling_ids
        assert "comment1" in ctx_map["comment2"].sibling_ids


# ---------------------------------------------------------------------------
# Deep reply chain (depth >= 2)
# ---------------------------------------------------------------------------


class TestDeepReplyChain:
    def _build(self):
        mentions = [
            make_mention("post1", "root post", root_id="post1"),
            make_mention(
                "comment1", "top comment", root_id="post1", parent_id="post1", depth=1
            ),
            make_mention(
                "reply1",
                "reply to comment",
                root_id="post1",
                parent_id="comment1",
                depth=2,
            ),
        ]
        return build_threads(mentions)

    def test_summary_reply_count(self):
        bundle = self._build()
        summary = bundle.summaries[0]
        assert summary.reply_count == 1

    def test_summary_max_depth(self):
        bundle = self._build()
        summary = bundle.summaries[0]
        assert summary.max_depth_observed == 2

    def test_reply_lineage_ids(self):
        bundle = self._build()
        ctx_map = {c.mention_id: c for c in bundle.contexts}
        reply_ctx = ctx_map["reply1"]
        # lineage: post1 → comment1 (ordered root-first)
        assert reply_ctx.lineage_ids == ["post1", "comment1"]

    def test_comment_direct_child_ids(self):
        bundle = self._build()
        ctx_map = {c.mention_id: c for c in bundle.contexts}
        assert "reply1" in ctx_map["comment1"].direct_child_ids


# ---------------------------------------------------------------------------
# Multiple independent root threads
# ---------------------------------------------------------------------------


class TestMultipleRoots:
    def _build(self):
        mentions = [
            make_mention("post1", "first post", root_id="post1"),
            make_mention(
                "c1", "comment on first", root_id="post1", parent_id="post1", depth=1
            ),
            make_mention("post2", "second post", root_id="post2"),
            make_mention(
                "c2", "comment on second", root_id="post2", parent_id="post2", depth=1
            ),
        ]
        return build_threads(mentions)

    def test_two_summaries(self):
        bundle = self._build()
        assert len(bundle.summaries) == 2

    def test_root_ids_distinct(self):
        bundle = self._build()
        root_ids = {s.root_id for s in bundle.summaries}
        assert root_ids == {"post1", "post2"}

    def test_edges_stay_within_thread(self):
        bundle = self._build()
        edge_map = {e.child_id: e.root_id for e in bundle.edges}
        assert edge_map["c1"] == "post1"
        assert edge_map["c2"] == "post2"

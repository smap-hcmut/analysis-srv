"""Threads module types — dataclass ports of core-analysis threads/models.py."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ThreadEdge:
    root_id: str
    parent_id: str
    child_id: str
    depth: int


@dataclass
class MentionContext:
    mention_id: str
    root_id: str
    parent_id: str | None = None
    lineage_ids: list[str] = field(default_factory=list)
    sibling_ids: list[str] = field(default_factory=list)
    direct_child_ids: list[str] = field(default_factory=list)
    context_text: str = ""
    root_text: str = ""
    parent_text: str | None = None


@dataclass
class ThreadSummary:
    root_id: str
    total_mentions: int
    total_descendants: int
    max_depth_observed: int
    comment_count: int
    reply_count: int
    top_comment_ids: list[str] = field(default_factory=list)
    top_comment_scores: list[float] = field(default_factory=list)


@dataclass
class ThreadBundle:
    summaries: list[ThreadSummary] = field(default_factory=list)
    edges: list[ThreadEdge] = field(default_factory=list)
    contexts: list[MentionContext] = field(default_factory=list)


__all__ = ["ThreadEdge", "MentionContext", "ThreadSummary", "ThreadBundle"]

"""build_threads.py — port of core-analysis threads/service.py.

Key adaptations from the original:
  - UAPType.COMMENT  →  mention.depth == 1
  - UAPType.REPLY    →  mention.depth >= 2
  - All models are local dataclasses (no pydantic BaseModel).
  - mention.likes / mention.sort_score accessed directly from MentionRecord.
"""

from __future__ import annotations

from collections import defaultdict

from internal.normalization.type import MentionRecord
from ..type import MentionContext, ThreadBundle, ThreadEdge, ThreadSummary


def _score_for_ranking(mention: MentionRecord) -> float:
    if mention.sort_score is not None:
        return mention.sort_score
    return 0.0


def _resolve_root_mention(
    root_id: str,
    thread_mentions: list[MentionRecord],
    mentions_by_id: dict[str, MentionRecord],
) -> MentionRecord:
    root_mention = mentions_by_id.get(root_id)
    if root_mention is not None:
        return root_mention
    return min(
        thread_mentions,
        key=lambda item: (
            item.depth,
            0 if item.parent_id is None or item.parent_id not in mentions_by_id else 1,
            item.mention_id,
        ),
    )


def build_threads(mentions: list[MentionRecord]) -> ThreadBundle:
    """Group mentions by root_id and build per-thread context."""
    mentions_by_id: dict[str, MentionRecord] = {m.mention_id: m for m in mentions}
    by_root: dict[str, list[MentionRecord]] = defaultdict(list)
    children_by_parent: dict[str, list[MentionRecord]] = defaultdict(list)
    edges: list[ThreadEdge] = []

    for mention in mentions:
        by_root[mention.root_id].append(mention)
        if mention.parent_id:
            children_by_parent[mention.parent_id].append(mention)
            edges.append(
                ThreadEdge(
                    root_id=mention.root_id,
                    parent_id=mention.parent_id,
                    child_id=mention.mention_id,
                    depth=mention.depth,
                )
            )

    contexts: list[MentionContext] = []
    summaries: list[ThreadSummary] = []

    for root_id, thread_mentions in by_root.items():
        sorted_mentions = sorted(
            thread_mentions, key=lambda item: (item.depth, item.mention_id)
        )
        root_mention = _resolve_root_mention(root_id, thread_mentions, mentions_by_id)

        # depth == 1 → comment (direct reply to root)
        # depth >= 2 → reply (reply to a comment or deeper)
        comments = [item for item in thread_mentions if item.depth == 1]
        replies = [item for item in thread_mentions if item.depth >= 2]
        ranked_comments = sorted(comments, key=_score_for_ranking, reverse=True)

        summaries.append(
            ThreadSummary(
                root_id=root_id,
                total_mentions=len(thread_mentions),
                total_descendants=max(len(thread_mentions) - 1, 0),
                max_depth_observed=max(item.depth for item in thread_mentions),
                comment_count=len(comments),
                reply_count=len(replies),
                top_comment_ids=[item.mention_id for item in ranked_comments[:5]],
                top_comment_scores=[
                    _score_for_ranking(item) for item in ranked_comments[:5]
                ],
            )
        )

        for mention in sorted_mentions:
            lineage_ids: list[str] = []
            current_parent = mention.parent_id
            while current_parent:
                lineage_ids.append(current_parent)
                parent_mention = mentions_by_id.get(current_parent)
                current_parent = (
                    parent_mention.parent_id if parent_mention is not None else None
                )
            lineage_ids.reverse()

            parent_text = (
                mentions_by_id[mention.parent_id].raw_text
                if mention.parent_id is not None and mention.parent_id in mentions_by_id
                else None
            )
            sibling_ids = [
                sibling.mention_id
                for sibling in children_by_parent.get(mention.parent_id or "", [])
                if sibling.mention_id != mention.mention_id
            ]
            direct_child_ids = [
                child.mention_id
                for child in children_by_parent.get(mention.mention_id, [])
            ]

            context_parts = [root_mention.raw_text]
            if parent_text and parent_text != root_mention.raw_text:
                context_parts.append(parent_text)
            if mention.raw_text not in context_parts:
                context_parts.append(mention.raw_text)

            contexts.append(
                MentionContext(
                    mention_id=mention.mention_id,
                    root_id=root_id,
                    parent_id=mention.parent_id,
                    lineage_ids=lineage_ids,
                    sibling_ids=sibling_ids,
                    direct_child_ids=direct_child_ids,
                    context_text=" | ".join(context_parts),
                    root_text=root_mention.raw_text,
                    parent_text=parent_text,
                )
            )

    return ThreadBundle(summaries=summaries, edges=edges, contexts=contexts)


__all__ = ["build_threads"]

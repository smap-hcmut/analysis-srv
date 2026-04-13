"""Helpers for enrichment — build MentionContext list from thread bundle or stubs.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from typing import Any

from internal.threads.type import MentionContext


def build_mention_contexts(
    mentions: list[Any],  # list[MentionRecord]
    thread_bundle: Any | None,  # ThreadBundle | None
) -> list[MentionContext]:
    """Build a MentionContext list from ThreadBundle or stubs.

    If thread_bundle is provided and has contexts, use them directly.
    Otherwise, create a stub MentionContext per mention with minimal data
    (root_id = mention.root_id or mention.mention_id, context_text = raw_text).
    """
    if thread_bundle is not None and thread_bundle.contexts:
        return list(thread_bundle.contexts)

    # Build stubs
    contexts: list[MentionContext] = []
    for mention in mentions:
        root_id = getattr(mention, "root_id", None) or mention.mention_id
        parent_id = getattr(mention, "parent_id", None)
        contexts.append(
            MentionContext(
                mention_id=mention.mention_id,
                root_id=root_id,
                parent_id=parent_id,
                context_text=mention.raw_text,
                root_text=mention.raw_text,
            )
        )
    return contexts

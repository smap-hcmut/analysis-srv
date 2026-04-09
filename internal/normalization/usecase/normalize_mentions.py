"""normalize_mentions — converts IngestedBatchBundle → NormalizationBatch.

Builds a MentionRecord for every UAPRecord in the batch by:
1. Deriving depth / root_id (reusing ingestion helpers)
2. Running normalize_social_text() for text / language / quality fields
3. Assembling MentionRecord with all required fields
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from internal.pipeline.type import IngestedBatchBundle
from internal.model.uap import UAPRecord
from internal.ingestion.constant import DOC_TYPE_DEPTH
from ..type import MentionRecord, NormalizationBatch
from .helpers import normalize_social_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_mention_id(project_id: str, doc_id: str) -> str:
    """Derive a deterministic UUID5 for a (project_id, doc_id) pair."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID namespace URL
    return str(uuid.uuid5(namespace, f"{project_id}:{doc_id}"))


def _parse_posted_at(published_at: Optional[str]) -> Optional[datetime]:
    if not published_at:
        return None
    try:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _build_depth_map(records: list[UAPRecord]) -> dict[str, int]:
    """Map doc_id → depth for all records in the batch."""
    return {
        r.content.doc_id: DOC_TYPE_DEPTH.get(r.content.doc_type, 0) for r in records
    }


def _derive_root_id(record: UAPRecord, depth_map: dict[str, int]) -> str:
    """Walk the parent chain within the batch to find the root_id."""
    doc_id = record.content.doc_id
    depth = DOC_TYPE_DEPTH.get(record.content.doc_type, 0)
    if depth == 0:
        return doc_id
    parent_id = record.content.parent.parent_id
    visited: set[str] = {doc_id}
    while parent_id and parent_id not in visited:
        visited.add(parent_id)
        parent_depth = depth_map.get(parent_id)
        if parent_depth is not None and parent_depth == 0:
            return parent_id
        # Cannot walk further without full records — stop
        break
    return parent_id or doc_id


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def normalize_mentions(batch: IngestedBatchBundle) -> NormalizationBatch:
    """Convert an IngestedBatchBundle into a NormalizationBatch."""
    depth_map = _build_depth_map(batch.records)
    mentions: list[MentionRecord] = []

    for record in batch.records:
        doc_id = record.content.doc_id
        project_id = record.ingest.project_id or batch.project_id
        depth = DOC_TYPE_DEPTH.get(record.content.doc_type, 0)
        root_id = _derive_root_id(record, depth_map)
        parent_id = record.content.parent.parent_id

        # Text normalization
        raw_text = record.content.text or ""
        explicit_language = record.content.language
        norm = normalize_social_text(raw_text, None, explicit_language)

        mention_id = _stable_mention_id(project_id, doc_id)
        author_id = (
            record.content.author.author_id
            or record.content.author.display_name
            or "unknown"
        )

        # Compute sort_score from engagement signals (likes + shares + views/100)
        eng = record.signals.engagement
        sort_score: Optional[float] = None
        if any(
            v > 0
            for v in (
                eng.like_count,
                eng.share_count,
                eng.view_count,
                eng.comment_count,
            )
        ):
            sort_score = float(
                eng.like_count
                + eng.share_count * 2
                + eng.comment_count * 3
                + eng.view_count // 100
            )

        mention = MentionRecord(
            mention_id=mention_id,
            source_uap_id=record.event_id,
            origin_id=doc_id,
            platform=record.ingest.source.source_type.lower(),
            project_id=project_id,
            root_id=root_id,
            parent_id=parent_id,
            depth=depth,
            author_id=author_id,
            author_username=record.content.author.username,
            raw_text=norm.raw_text,
            normalized_text=norm.normalized_text,
            normalized_text_compact=norm.normalized_text_compact,
            language=norm.language,
            language_confidence=norm.language_confidence,
            language_supported=norm.language_supported,
            language_rejection_reason=norm.language_rejection_reason,
            mixed_language_uncertain=norm.mixed_language_uncertain,
            text_quality_label=norm.text_quality_label,
            text_quality_flags=norm.text_quality_flags,
            text_quality_score=norm.text_quality_score,
            hashtags=norm.hashtags,
            urls=norm.urls,
            emojis=norm.emojis,
            semantic_route_hint=norm.semantic_route_hint,
            source_url=record.content.url,
            posted_at=_parse_posted_at(record.content.published_at),
            likes=eng.like_count if eng.like_count > 0 else None,
            comments_count=eng.comment_count if eng.comment_count > 0 else None,
            shares=eng.share_count if eng.share_count > 0 else None,
            views=eng.view_count if eng.view_count > 0 else None,
            sort_score=sort_score,
        )
        mentions.append(mention)

    return NormalizationBatch(mentions=mentions)


__all__ = ["normalize_mentions"]

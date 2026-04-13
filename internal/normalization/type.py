"""Normalization types — MentionRecord is the silver-layer record produced by
the normalization stage.  Uses dataclasses (not pydantic) per analysis-srv convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class MentionRecord:
    """Normalized representation of a single social mention (post/comment/reply)."""

    # Identity
    mention_id: str = ""
    source_uap_id: str = ""
    origin_id: str = ""  # doc_id from UAPRecord.content
    platform: str = ""
    project_id: str = ""

    # Hierarchy
    root_id: str = ""
    parent_id: Optional[str] = None
    depth: int = 0

    # Author
    author_id: str = ""
    author_username: Optional[str] = None

    # Text
    raw_text: str = ""
    normalized_text: str = ""
    normalized_text_compact: str = ""

    # Language
    language: str = "unknown"
    language_confidence: float = 0.0
    language_supported: bool = True
    language_rejection_reason: Optional[str] = None
    mixed_language_uncertain: bool = False

    # Text quality
    text_quality_label: str = "normal"
    text_quality_flags: list[str] = field(default_factory=list)
    text_quality_score: float = 1.0

    # Extracted tokens
    hashtags: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    emojis: list[str] = field(default_factory=list)

    # Routing hint for downstream stages
    semantic_route_hint: str = "semantic_full"

    # Dedup annotations (populated by dedup stage)
    dedup_cluster_id: Optional[str] = None
    dedup_kind: Optional[str] = None
    dedup_representative_mention_id: Optional[str] = None
    dedup_cluster_size: int = 1
    dedup_similarity: Optional[float] = None
    dedup_weight: float = 1.0

    # Spam / quality annotations (populated by spam stage)
    mention_spam_score: float = 0.0
    author_inorganic_score: float = 0.0
    mention_suspicious: bool = False
    author_suspicious: bool = False
    suspicion_reason_codes: list[str] = field(default_factory=list)
    quality_weight: float = 1.0

    # Metadata
    source_url: Optional[str] = None
    posted_at: Optional[datetime] = None

    # Engagement signals
    likes: Optional[int] = None
    comments_count: Optional[int] = None
    shares: Optional[int] = None
    views: Optional[int] = None
    sort_score: Optional[float] = None


@dataclass
class NormalizationBatch:
    """Output of the normalization stage."""

    mentions: list[MentionRecord] = field(default_factory=list)
    filtered_out_records: int = 0
    filtered_out_unsupported_language: int = 0


__all__ = ["MentionRecord", "NormalizationBatch"]

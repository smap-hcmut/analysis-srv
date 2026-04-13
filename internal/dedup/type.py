"""Dedup module types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DedupClusterRecord:
    dedup_cluster_id: str
    dedup_kind: str  # "exact" | "near"
    representative_mention_id: str
    representative_text: str
    mention_ids: list[str] = field(default_factory=list)
    cluster_size: int = 0
    similarity_proxy: float = 0.0
    text_fingerprint: Optional[str] = None


@dataclass
class DedupAnalysisResult:
    mentions_updated: int = 0
    exact_cluster_count: int = 0
    near_cluster_count: int = 0
    clusters: list[DedupClusterRecord] = field(default_factory=list)


__all__ = ["DedupClusterRecord", "DedupAnalysisResult"]

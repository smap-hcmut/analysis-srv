"""Simplified entity enricher — regex-based candidate extraction.

Ported from core-analysis smap/enrichers/entity.py but simplified:
- No CanonicalizationEngine, OntologyRegistry, NERProvider
- Extract @mentions, #hashtags, CAPITALIZED noun phrases via regex
- All results are unresolved_candidate (Phase 4 limitation)
- annotate_batch_local_candidates clusters by normalize_alias()

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from typing import Any

from internal.enrichment.type import (
    EntityCandidateClusterFact,
    EntityFact,
    FactProvenance,
)
from internal.enrichment.usecase._anchors import normalize_alias

# ---------------------------------------------------------------------------
# Regex patterns for candidate extraction
# ---------------------------------------------------------------------------

_MENTION_RE = re.compile(r"@([\w.]+)", flags=re.UNICODE)
_HASHTAG_RE = re.compile(r"#([\w]+)", flags=re.UNICODE)
# 2-4 tokens, each starting with uppercase or Vietnamese capitalized char
_CAPITALIZED_PHRASE_RE = re.compile(
    r"\b([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][a-zàáâãèéêìíòóôõùúăđĩũơưạ-ỹ]*"
    r"(?:\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][a-zàáâãèéêìíòóôõùúăđĩũơưạ-ỹ]*){0,3})\b",
    flags=re.UNICODE,
)
# Min length for a capitalized phrase candidate
_MIN_PHRASE_LEN = 3
# Words to ignore as entity candidates (common Vietnamese/English stopwords)
_STOPWORD_SET = frozenset(
    {
        "The",
        "This",
        "That",
        "These",
        "Those",
        "There",
        "Here",
        "I",
        "You",
        "He",
        "She",
        "We",
        "They",
        "It",
        "My",
        "Your",
        "Our",
        "His",
        "Her",
        "Its",
        "Their",
        "And",
        "But",
        "Or",
        "For",
        "Nor",
        "So",
        "Yet",
        "Và",
        "Của",
        "Cho",
        "Với",
        "Trong",
        "Trên",
        "Dưới",
        "Nếu",
        "Khi",
        "Vì",
        "Bởi",
    }
)


def _extract_raw_candidates(text: str) -> list[str]:
    """Extract entity candidate strings from raw text."""
    candidates: list[str] = []

    # @username mentions
    for match in _MENTION_RE.finditer(text):
        name = match.group(1)
        if len(name) >= 2:
            candidates.append(f"@{name}")

    # #hashtag — normalize to lowercase without #
    for match in _HASHTAG_RE.finditer(text):
        tag = match.group(1)
        if len(tag) >= 3:
            candidates.append(f"#{tag.lower()}")

    # Capitalized noun phrases
    for match in _CAPITALIZED_PHRASE_RE.finditer(text):
        phrase = match.group(1).strip()
        if len(phrase) >= _MIN_PHRASE_LEN and phrase not in _STOPWORD_SET:
            candidates.append(phrase)

    # Dedup preserving first occurrence order
    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in candidates:
        key = normalize_alias(candidate)
        if key and key not in seen:
            seen.add(key)
            deduped.append(candidate)

    return deduped


# ---------------------------------------------------------------------------
# SimplifiedEntityEnricher
# ---------------------------------------------------------------------------


class SimplifiedEntityEnricher:
    """Simplified entity extractor — all outputs are unresolved_candidate."""

    provider_version = "entity-simplified-v1"
    name = "entity"

    def __init__(self) -> None:
        self._candidates_by_mention: dict[str, list[str]] = {}

    def prepare(
        self,
        mentions: list[Any],  # list[MentionRecord]
        contexts: list[Any],  # list[MentionContext]
    ) -> None:
        """Pre-scan all mentions to build per-mention candidate lists."""
        del contexts
        self._candidates_by_mention = {}
        for mention in mentions:
            candidates = _extract_raw_candidates(mention.raw_text)
            # Pre-compute normalised set once — avoids O(n²) rebuild per hashtag
            normalized_candidates = {normalize_alias(c) for c in candidates}
            # Also include hashtags already extracted by normalization stage
            for hashtag in mention.hashtags:
                tag_key = normalize_alias(hashtag)
                if tag_key and tag_key not in normalized_candidates:
                    candidates.append(f"#{hashtag.lower()}")
                    normalized_candidates.add(tag_key)
            self._candidates_by_mention[mention.mention_id] = candidates[:8]

    def enrich(
        self,
        mention: Any,  # MentionRecord
        context: Any,  # MentionContext | None
    ) -> list[EntityFact]:
        """Return EntityFacts for all extracted candidates (all unresolved)."""
        candidates = self._candidates_by_mention.get(
            mention.mention_id,
            _extract_raw_candidates(mention.raw_text)[:8],
        )
        if not candidates:
            return []

        facts: list[EntityFact] = []
        evidence_text = (
            context.context_text if context is not None else mention.raw_text
        )
        for candidate_text in candidates:
            entity_type = _infer_entity_type(candidate_text)
            facts.append(
                EntityFact(
                    mention_id=mention.mention_id,
                    source_uap_id=mention.source_uap_id,
                    candidate_text=candidate_text,
                    canonical_entity_id=None,
                    concept_entity_id=None,
                    entity_type=entity_type,
                    confidence=0.4,
                    matched_by="regex_extraction",
                    resolution_kind="unresolved_candidate",
                    resolved_entity_kind=None,
                    knowledge_layer=None,
                    target_eligible=False,
                    unresolved_cluster_id=None,
                    unresolved_cluster_size=0,
                    surface_specificity=_surface_specificity(candidate_text),
                    unresolved_reason="no_candidate_found",
                    canonical_candidate_ids=[],
                    discovered_by=["regex_extraction"],
                    provenance=FactProvenance(
                        source_uap_id=mention.source_uap_id,
                        mention_id=mention.mention_id,
                        provider_version=self.provider_version,
                        rule_version="entity-simplified-v1",
                        evidence_text=evidence_text,
                    ),
                )
            )
        return facts

    def annotate_batch_local_candidates(
        self,
        entity_facts: list[EntityFact],
        mentions: list[Any],  # list[MentionRecord]
    ) -> tuple[list[EntityFact], list[EntityCandidateClusterFact]]:
        """Cluster unresolved facts by normalize_alias(candidate_text).

        Assigns cluster_id and cluster_size back onto each EntityFact.
        Returns (updated_entity_facts, cluster_facts).
        """
        # Build cluster map: normalized_surface → list of (index, fact)
        clusters: dict[str, list[tuple[int, EntityFact]]] = defaultdict(list)
        for index, fact in enumerate(entity_facts):
            if fact.resolution_kind != "unresolved_candidate":
                continue
            surface = (
                normalize_alias(fact.candidate_text) or fact.candidate_text.casefold()
            )
            clusters[surface].append((index, fact))

        mention_languages: dict[str, str] = {
            mention.mention_id: getattr(mention, "language", "unknown")
            for mention in mentions
        }

        cluster_facts: list[EntityCandidateClusterFact] = []
        updated = list(entity_facts)

        for normalized_surface, items in clusters.items():
            if not items:
                continue
            cluster_id = _cluster_id(normalized_surface)
            representative_surface = items[0][1].candidate_text
            mention_ids = list(dict.fromkeys(fact.mention_id for _, fact in items))
            source_languages = list(
                dict.fromkeys(
                    mention_languages.get(fact.mention_id, "unknown")
                    for _, fact in items
                )
            )
            entity_type_hint = next(
                (fact.entity_type for _, fact in items if fact.entity_type), None
            )

            # Update each fact with cluster info
            for index, fact in items:
                updated[index] = fact.model_copy(
                    update={
                        "unresolved_cluster_id": cluster_id,
                        "unresolved_cluster_size": len(items),
                        "knowledge_layer": "batch_local_candidate",
                    }
                )

            if len(items) > 1:
                cluster_facts.append(
                    EntityCandidateClusterFact(
                        cluster_id=cluster_id,
                        normalized_surface=normalized_surface,
                        representative_surface=representative_surface,
                        knowledge_layer="batch_local_candidate",
                        entity_type_hint=entity_type_hint,
                        mention_count=len(mention_ids),
                        source_languages=source_languages,
                        discovered_by=["regex_extraction"],
                        representative_mention_ids=mention_ids[:5],
                        candidate_canonical_ids=[],
                        promotion_state="reviewable",
                        provenance=FactProvenance(
                            source_uap_id="batch_local",
                            mention_id=mention_ids[0],
                            provider_version=self.provider_version,
                            rule_version="entity-cluster-simplified-v1",
                            evidence_text=normalized_surface,
                        ),
                    )
                )

        return updated, cluster_facts


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _infer_entity_type(candidate_text: str) -> str | None:
    """Infer a coarse entity type from the candidate surface form."""
    if candidate_text.startswith("@"):
        return "person"
    if candidate_text.startswith("#"):
        return None  # topic/hashtag — no clear entity type
    # Multi-word phrase → likely organization/product
    tokens = candidate_text.split()
    if len(tokens) >= 2:
        return "organization"
    return None


def _surface_specificity(candidate_text: str) -> float:
    """Estimate surface specificity — longer and multi-token text scores higher."""
    stripped = candidate_text.lstrip("@#")
    length_score = min(len(stripped) / 20.0, 1.0)
    token_score = min(len(stripped.split()) / 3.0, 1.0)
    return round((length_score * 0.6 + token_score * 0.4), 3)


def _cluster_id(normalized_surface: str) -> str:
    digest = hashlib.md5(
        normalized_surface.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:12]
    return f"blc-{digest}"

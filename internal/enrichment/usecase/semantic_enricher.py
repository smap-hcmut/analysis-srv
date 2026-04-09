"""Simplified semantic inference enricher — ported from core-analysis semantic.py.

Simplifications vs core-analysis SemanticInferenceEnricher:
- No parallel workers, no runtime diagnostics, no caches
- No semantic_assist (requires TaxonomyMappingProvider)
- No reranker, no embedding_provider, no prototype_registry
- No promoted_semantic_knowledge
- No OntologyRegistry

Key behaviour preserved:
- Segmentation via SemanticSegmenter
- Lexical anchor extraction (polarity, aspect, issue, negation, uncertainty, etc.)
- Mention-level sentiment aggregation (_aggregate_mention_sentiment)
- Thread & aspect corroboration using token Jaccard similarity
- _apply_thread_corroboration, _apply_aspect_corroboration (numpy)
- _build_mention_sentiment_fact produces real SentimentFact

Phase 4 known limitations (empty because all entity facts are unresolved_candidate):
- target_sentiments → []
- aspect_opinions → []
- issue_signals → []

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from internal.enrichment.type import (
    AspectOpinionFact,
    EntityFact,
    FactProvenance,
    IssueSignalFact,
    SentimentFact,
    TargetSentimentFact,
)
from internal.enrichment.usecase._anchors import (
    ASPECT_SEEDS,
    ISSUE_SEEDS,
    contains_first_person,
    extract_lexical_anchors,
    normalize_alias,
)
from internal.enrichment.usecase._calibration import (
    clamp_confidence,
    issue_confidence_components,
    sentiment_confidence_components,
)
from internal.enrichment.usecase._segmenter import SemanticSegmenter
from internal.enrichment.usecase._semantic_models import (
    AnchorType,
    AspectOpinionHypothesis,
    EvidenceMode,
    EvidenceScope,
    EvidenceSpan,
    IssueSignalHypothesis,
    MentionSentimentHypothesis,
    ScoreComponent,
    SemanticAnchor,
    SemanticHypothesisBatch,
    SemanticSegment,
    TargetReference,
    TargetSentimentHypothesis,
)

SentimentValue = Literal["positive", "negative", "neutral", "mixed"]

_SCOPE_MATCH_CHARS = 48
_CORROBORATION_SIMILARITY_THRESHOLD = 0.52
_CORROBORATION_PAIRWISE_MAX_GROUP = 96


@dataclass(slots=True)
class SemanticInferenceResult:
    mention_sentiments: list[SentimentFact]
    target_sentiments: list[TargetSentimentFact]
    aspect_opinions: list[AspectOpinionFact]
    issue_signals: list[IssueSignalFact]


class SimplifiedSemanticInferenceEnricher:
    """Simplified port of SemanticInferenceEnricher.

    Produces SentimentFact per mention via lexical polarity analysis.
    TargetSentimentFact, AspectOpinionFact, IssueSignalFact are all empty
    in Phase 4 because all entity facts are unresolved_candidate (no grounded targets).
    """

    provider_version = "semantic-local-simplified-v1"

    def __init__(self) -> None:
        self.segmenter = SemanticSegmenter()

    def enrich(
        self,
        mentions: list[Any],  # list[MentionRecord]
        contexts: list[Any],  # list[MentionContext]
        entity_facts: list[EntityFact],
    ) -> SemanticInferenceResult:
        mention_map = {mention.mention_id: mention for mention in mentions}
        # In Phase 4 all entity facts are unresolved → no grounded targets
        explicit_targets_by_mention: dict[str, list[TargetReference]] = {
            mention.mention_id: [] for mention in mentions
        }
        hypotheses = self._collect_hypotheses_serial(
            mentions=mentions,
            contexts=contexts,
            explicit_targets_by_mention=explicit_targets_by_mention,
        )
        mention_hypotheses = hypotheses.mention_sentiments
        issue_hypotheses = self._apply_thread_corroboration(
            mentions=mention_map,
            issue_hypotheses=hypotheses.issue_signals,
        )
        aspect_hypotheses = self._apply_aspect_corroboration(
            mentions=mention_map,
            aspect_hypotheses=hypotheses.aspect_opinions,
        )
        return SemanticInferenceResult(
            mention_sentiments=[
                self._build_mention_sentiment_fact(item, mention_map[item.mention_id])
                for item in mention_hypotheses
            ],
            target_sentiments=[
                self._build_target_sentiment_fact(item, mention_map[item.mention_id])
                for item in hypotheses.target_sentiments
            ],
            aspect_opinions=[
                self._build_aspect_fact(item, mention_map[item.mention_id])
                for item in aspect_hypotheses
            ],
            issue_signals=[
                self._build_issue_fact(item, mention_map[item.mention_id])
                for item in issue_hypotheses
            ],
        )

    # ------------------------------------------------------------------
    # Hypothesis collection
    # ------------------------------------------------------------------

    def _collect_hypotheses_serial(
        self,
        *,
        mentions: list[Any],
        contexts: list[Any],
        explicit_targets_by_mention: dict[str, list[TargetReference]],
    ) -> SemanticHypothesisBatch:
        context_map = {context.mention_id: context for context in contexts}
        batch = SemanticHypothesisBatch()
        for mention in mentions:
            context = context_map.get(mention.mention_id)
            explicit_targets = explicit_targets_by_mention.get(mention.mention_id, [])
            # No inherited targets in Phase 4 (all entities are unresolved)
            inherited_targets: list[TargetReference] = []
            results = self._analyze_mention(
                mention,
                explicit_targets=explicit_targets,
                inherited_targets=inherited_targets,
            )
            batch.mention_sentiments.extend(results[0])
            batch.target_sentiments.extend(results[1])
            batch.aspect_opinions.extend(results[2])
            batch.issue_signals.extend(results[3])
        return batch

    def _analyze_mention(
        self,
        mention: Any,
        *,
        explicit_targets: list[TargetReference],
        inherited_targets: list[TargetReference],
    ) -> tuple[
        list[MentionSentimentHypothesis],
        list[TargetSentimentHypothesis],
        list[AspectOpinionHypothesis],
        list[IssueSignalHypothesis],
    ]:
        segments = self.segmenter.segment(mention.raw_text)
        if not segments:
            return ([], [], [], [])

        segment_sentiments: list[
            tuple[SemanticSegment, float, list[SemanticAnchor], list[str], bool]
        ] = []
        target_segment_hypotheses: list[TargetSentimentHypothesis] = []
        aspect_segment_hypotheses: list[AspectOpinionHypothesis] = []
        issue_segment_hypotheses: list[IssueSignalHypothesis] = []

        routing_mode = self._semantic_routing_mode(mention)

        for segment in segments:
            anchors = extract_lexical_anchors(
                segment,
                aspect_seeds=ASPECT_SEEDS,
                issue_seeds=ISSUE_SEEDS,
            )
            anchors.sort(
                key=lambda item: (item.start, item.end, item.anchor_type.value)
            )
            polarity_score, polarity_supports, negated = self._segment_polarity(anchors)
            uncertainty_flags = self._uncertainty_flags(segment, anchors)
            segment_sentiments.append(
                (segment, polarity_score, anchors, uncertainty_flags, negated)
            )

            # No grounded targets → target_sentiments, aspect_opinions, issue_signals are []
            # (explicit_targets is [] in Phase 4)
            if polarity_supports and explicit_targets:
                target_segment_hypotheses.extend(
                    self._segment_target_sentiments(
                        mention=mention,
                        segment=segment,
                        anchors=anchors,
                        explicit_targets=explicit_targets,
                        inherited_targets=inherited_targets,
                        polarity_score=polarity_score,
                        polarity_supports=polarity_supports,
                        negated=negated,
                        uncertainty_flags=uncertainty_flags,
                        routing_mode=routing_mode,
                    )
                )

        mention_hypothesis = self._aggregate_mention_sentiment(
            mention, segment_sentiments
        )
        target_hypotheses = self._merge_target_hypotheses(target_segment_hypotheses)
        aspect_hypotheses = self._merge_aspect_hypotheses(aspect_segment_hypotheses)

        return (
            [mention_hypothesis] if mention_hypothesis is not None else [],
            target_hypotheses,
            aspect_hypotheses,
            issue_segment_hypotheses,
        )

    # ------------------------------------------------------------------
    # Polarity & uncertainty
    # ------------------------------------------------------------------

    def _segment_polarity(
        self,
        anchors: list[SemanticAnchor],
    ) -> tuple[float, list[SemanticAnchor], bool]:
        polarity_anchors = [
            anchor for anchor in anchors if anchor.anchor_type == AnchorType.POLARITY
        ]
        adjusted_total = 0.0
        supports: list[SemanticAnchor] = []
        negated = False
        for anchor in polarity_anchors:
            if anchor.polarity is None:
                continue
            score = self._cue_score(anchor, anchors)
            if score != anchor.polarity:
                negated = True
            adjusted_total += score
            supports.append(anchor)
        return adjusted_total, supports, negated

    def _uncertainty_flags(
        self,
        segment: SemanticSegment,
        anchors: list[SemanticAnchor],
    ) -> list[str]:
        flags: list[str] = []
        if segment.question_like or any(
            anchor.anchor_type == AnchorType.UNCERTAINTY for anchor in anchors
        ):
            flags.append("question_or_uncertainty")
        if any(anchor.anchor_type == AnchorType.HEARSAY for anchor in anchors):
            flags.append("hearsay_or_rumor")
        if any(anchor.anchor_type == AnchorType.COMPARISON for anchor in anchors):
            flags.append("comparison")
        if any(anchor.anchor_type == AnchorType.CONTRAST for anchor in anchors):
            flags.append("contrast")
        return flags

    def _cue_score(
        self,
        cue: SemanticAnchor,
        anchors: list[SemanticAnchor],
    ) -> float:
        polarity = cue.polarity or 0.0
        negation_anchors = [
            anchor for anchor in anchors if anchor.anchor_type == AnchorType.NEGATION
        ]
        if any(0 <= cue.start - neg.start <= 14 for neg in negation_anchors):
            return -polarity
        return polarity

    # ------------------------------------------------------------------
    # Mention-level sentiment aggregation
    # ------------------------------------------------------------------

    def _aggregate_mention_sentiment(
        self,
        mention: Any,
        segment_sentiments: list[
            tuple[SemanticSegment, float, list[SemanticAnchor], list[str], bool]
        ],
    ) -> MentionSentimentHypothesis | None:
        if not segment_sentiments:
            return None
        total_score = sum(score for _, score, _, _, _ in segment_sentiments)
        segment_labels = [
            self._sentiment_label(score) for _, score, _, _, _ in segment_sentiments
        ]
        evidence_spans = [
            anchor.to_evidence_span()
            for _, _, anchors, _, _ in segment_sentiments
            for anchor in anchors
            if anchor.anchor_type == AnchorType.POLARITY
        ]
        uncertainty_flags = sorted(
            {flag for _, _, _, flags, _ in segment_sentiments for flag in flags}
        )
        sentiment = self._merge_sentiment_labels(segment_labels)
        components = sentiment_confidence_components(
            explicit_target=False,
            inherited_target=False,
            support_count=len(evidence_spans),
            mixed_evidence=sentiment == "mixed",
            contrastive=any(
                segment.contrastive for segment, _, _, _, _ in segment_sentiments
            ),
            negated=any(negated for _, _, _, _, negated in segment_sentiments),
            uncertain=bool(uncertainty_flags),
        )
        confidence = clamp_confidence(0.5, components)
        return MentionSentimentHypothesis(
            mention_id=mention.mention_id,
            sentiment=sentiment,
            confidence=confidence,
            score=round(abs(total_score), 3),
            semantic_routing=self._semantic_routing_mode(mention),
            corroboration_confidence=0.65,
            evidence_spans=evidence_spans,
            score_components=components,
            uncertainty_flags=uncertainty_flags,
            segment_ids=[
                segment.segment_id for segment, _, _, _, _ in segment_sentiments
            ],
        )

    # ------------------------------------------------------------------
    # Target sentiment (Phase 4: always returns [] since no grounded targets)
    # ------------------------------------------------------------------

    def _segment_target_sentiments(
        self,
        *,
        mention: Any,
        segment: SemanticSegment,
        anchors: list[SemanticAnchor],
        explicit_targets: list[TargetReference],
        inherited_targets: list[TargetReference],
        polarity_score: float,
        polarity_supports: list[SemanticAnchor],
        negated: bool,
        uncertainty_flags: list[str],
        routing_mode: str,
    ) -> list[TargetSentimentHypothesis]:
        # In Phase 4, all entity facts are unresolved_candidate → no grounded targets
        return []

    def _merge_target_hypotheses(
        self,
        hypotheses: list[TargetSentimentHypothesis],
    ) -> list[TargetSentimentHypothesis]:
        if not hypotheses:
            return []
        grouped: dict[tuple[str, str], list[TargetSentimentHypothesis]] = defaultdict(
            list
        )
        for hypothesis in hypotheses:
            grouped[(hypothesis.mention_id, hypothesis.target.target_key)].append(
                hypothesis
            )
        merged: list[TargetSentimentHypothesis] = []
        for items in grouped.values():
            merged.append(
                TargetSentimentHypothesis(
                    mention_id=items[0].mention_id,
                    target=items[0].target,
                    sentiment=self._merge_sentiment_labels(
                        [item.sentiment for item in items]
                    ),
                    confidence=round(
                        sum(item.confidence for item in items) / len(items), 3
                    ),
                    score=round(max(item.score for item in items), 3),
                    semantic_routing=items[0].semantic_routing,
                    target_grounding_confidence=max(
                        item.target_grounding_confidence or 0.0 for item in items
                    ),
                    corroboration_confidence=max(
                        item.corroboration_confidence or 0.0 for item in items
                    ),
                    evidence_scope=self._merge_evidence_scope(
                        [item.evidence_scope for item in items]
                    ),
                    evidence_spans=[
                        span for item in items for span in item.evidence_spans
                    ],
                    score_components=[
                        component
                        for item in items
                        for component in item.score_components
                    ],
                    uncertainty_flags=sorted(
                        {flag for item in items for flag in item.uncertainty_flags}
                    ),
                    segment_ids=sorted(
                        {
                            segment_id
                            for item in items
                            for segment_id in item.segment_ids
                        }
                    ),
                )
            )
        return merged

    def _merge_aspect_hypotheses(
        self,
        hypotheses: list[AspectOpinionHypothesis],
    ) -> list[AspectOpinionHypothesis]:
        if not hypotheses:
            return []
        grouped: dict[tuple[str, str, str | None], list[AspectOpinionHypothesis]] = (
            defaultdict(list)
        )
        for hypothesis in hypotheses:
            grouped[
                (
                    hypothesis.mention_id,
                    hypothesis.aspect,
                    hypothesis.target.target_key
                    if hypothesis.target is not None
                    else None,
                )
            ].append(hypothesis)
        merged: list[AspectOpinionHypothesis] = []
        for items in grouped.values():
            first = items[0]
            merged.append(
                AspectOpinionHypothesis(
                    mention_id=first.mention_id,
                    aspect=first.aspect,
                    target=first.target,
                    sentiment=self._merge_sentiment_labels(
                        [item.sentiment for item in items]
                    ),
                    confidence=round(
                        sum(item.confidence for item in items) / len(items), 3
                    ),
                    semantic_routing=first.semantic_routing,
                    target_grounding_confidence=max(
                        item.target_grounding_confidence or 0.0 for item in items
                    ),
                    corroboration_confidence=max(
                        item.corroboration_confidence or 0.0 for item in items
                    ),
                    evidence_scope=self._merge_evidence_scope(
                        [item.evidence_scope for item in items]
                    ),
                    evidence_spans=[
                        span for item in items for span in item.evidence_spans
                    ],
                    score_components=[
                        component
                        for item in items
                        for component in item.score_components
                    ],
                    uncertainty_flags=sorted(
                        {flag for item in items for flag in item.uncertainty_flags}
                    ),
                    segment_id=first.segment_id,
                )
            )
        return merged

    # ------------------------------------------------------------------
    # Corroboration
    # ------------------------------------------------------------------

    def _apply_thread_corroboration(
        self,
        *,
        mentions: dict[str, Any],
        issue_hypotheses: list[IssueSignalHypothesis],
    ) -> list[IssueSignalHypothesis]:
        if not issue_hypotheses:
            return []
        grouped: dict[tuple[str, str, str | None], list[IssueSignalHypothesis]] = (
            defaultdict(list)
        )
        for issue in issue_hypotheses:
            mention = mentions[issue.mention_id]
            grouped[
                (
                    mention.root_id,
                    issue.issue_category,
                    issue.target.target_key if issue.target else None,
                )
            ].append(issue)
        corroboration_counts: dict[int, int] = {}
        for group in grouped.values():
            if len(group) > _CORROBORATION_PAIRWISE_MAX_GROUP:
                corroboration_counts.update(
                    self._large_group_corroboration_counts(
                        evidence_texts=[
                            self._issue_hypothesis_evidence_text(
                                issue, mentions[issue.mention_id]
                            )
                            for issue in group
                        ],
                        hypotheses=group,
                    )
                )
                continue
            evidence_texts = [
                self._issue_hypothesis_evidence_text(issue, mentions[issue.mention_id])
                for issue in group
            ]
            similarities = self._pairwise_token_jaccard(evidence_texts)
            similarity_matrix = np.asarray(similarities, dtype=np.float32)
            corroboration_vector = (
                similarity_matrix >= _CORROBORATION_SIMILARITY_THRESHOLD
            ).sum(axis=1)
            for index, issue in enumerate(group):
                corroboration_counts[id(issue)] = int(corroboration_vector[index])
        updated: list[IssueSignalHypothesis] = []
        for issue in issue_hypotheses:
            corroboration_count = corroboration_counts.get(id(issue), 1)
            components = issue_confidence_components(
                explicit_target=issue.target is not None
                and not issue.target.inherited
                and issue.evidence_scope == EvidenceScope.LOCAL,
                inherited_target=issue.target.inherited if issue.target else False,
                corroboration_count=corroboration_count,
                uncertain=bool(issue.uncertainty_flags),
                escalation=issue.evidence_mode == EvidenceMode.ESCALATION_SIGNAL,
                direct_mode=issue.evidence_mode
                in {EvidenceMode.DIRECT_COMPLAINT, EvidenceMode.DIRECT_OBSERVATION},
            )
            updated.append(
                IssueSignalHypothesis(
                    mention_id=issue.mention_id,
                    issue_category=issue.issue_category,
                    target=issue.target,
                    severity=self._bump_issue_severity(
                        issue.severity,
                        corroboration_count,
                        issue.evidence_mode,
                    ),
                    evidence_mode=issue.evidence_mode,
                    confidence=clamp_confidence(0.44, components),
                    evidence_scope=issue.evidence_scope,
                    evidence_spans=issue.evidence_spans,
                    score_components=components,
                    uncertainty_flags=issue.uncertainty_flags,
                    segment_id=issue.segment_id,
                    corroboration_count=corroboration_count,
                )
            )
        return updated

    def _apply_aspect_corroboration(
        self,
        *,
        mentions: dict[str, Any],
        aspect_hypotheses: list[AspectOpinionHypothesis],
    ) -> list[AspectOpinionHypothesis]:
        if not aspect_hypotheses:
            return []
        grouped: dict[
            tuple[str, str, str | None, str], list[AspectOpinionHypothesis]
        ] = defaultdict(list)
        for aspect in aspect_hypotheses:
            mention = mentions[aspect.mention_id]
            grouped[
                (
                    mention.root_id,
                    aspect.aspect,
                    aspect.target.target_key if aspect.target else None,
                    aspect.sentiment,
                )
            ].append(aspect)
        corroboration_counts: dict[int, int] = {}
        for group in grouped.values():
            if len(group) > _CORROBORATION_PAIRWISE_MAX_GROUP:
                corroboration_counts.update(
                    self._large_group_corroboration_counts(
                        evidence_texts=[
                            self._aspect_hypothesis_evidence_text(
                                aspect, mentions[aspect.mention_id]
                            )
                            for aspect in group
                        ],
                        hypotheses=group,
                    )
                )
                continue
            evidence_texts = [
                self._aspect_hypothesis_evidence_text(
                    aspect, mentions[aspect.mention_id]
                )
                for aspect in group
            ]
            similarities = self._pairwise_token_jaccard(evidence_texts)
            similarity_matrix = np.asarray(similarities, dtype=np.float32)
            corroboration_vector = (
                similarity_matrix >= _CORROBORATION_SIMILARITY_THRESHOLD
            ).sum(axis=1)
            for index, aspect in enumerate(group):
                corroboration_counts[id(aspect)] = int(corroboration_vector[index])
        updated: list[AspectOpinionHypothesis] = []
        for aspect in aspect_hypotheses:
            corroboration_count = corroboration_counts.get(id(aspect), 1)
            components = list(aspect.score_components)
            if corroboration_count > 1:
                components.append(
                    ScoreComponent(
                        name="semantic_corroboration",
                        value=round(min(corroboration_count / 4.0, 1.0), 4),
                        reason=f"thread-level semantic corroboration from {corroboration_count} similar aspect mentions",
                    )
                )
            updated.append(
                AspectOpinionHypothesis(
                    mention_id=aspect.mention_id,
                    aspect=aspect.aspect,
                    target=aspect.target,
                    sentiment=aspect.sentiment,
                    confidence=round(
                        min(
                            aspect.confidence + max(corroboration_count - 1, 0) * 0.03,
                            0.97,
                        ),
                        3,
                    ),
                    evidence_scope=aspect.evidence_scope,
                    evidence_spans=aspect.evidence_spans,
                    score_components=components,
                    uncertainty_flags=aspect.uncertainty_flags,
                    segment_id=aspect.segment_id,
                )
            )
        return updated

    # ------------------------------------------------------------------
    # Pairwise similarity (token Jaccard — no embedding_provider)
    # ------------------------------------------------------------------

    def _pairwise_token_jaccard(
        self,
        evidence_texts: list[str],
    ) -> list[list[float]]:
        if not evidence_texts:
            return []
        normalized = [normalize_alias(text) for text in evidence_texts]
        n = len(normalized)
        result = np.eye(n, dtype=np.float32)
        for row in range(n):
            for col in range(row + 1, n):
                score = (
                    1.0
                    if normalized[row] == normalized[col]
                    else self._token_jaccard(normalized[row], normalized[col])
                )
                result[row, col] = score
                result[col, row] = score
        return result.tolist()  # type: ignore[return-value]

    def _token_jaccard(self, left: str, right: str) -> float:
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        if not left_tokens and not right_tokens:
            return 1.0
        union = left_tokens | right_tokens
        if not union:
            return 0.0
        return len(left_tokens & right_tokens) / len(union)

    # ------------------------------------------------------------------
    # Evidence text helpers
    # ------------------------------------------------------------------

    def _issue_hypothesis_evidence_text(
        self,
        issue: IssueSignalHypothesis,
        mention: Any,
    ) -> str:
        if issue.evidence_spans:
            joined = " ".join(
                span.text for span in issue.evidence_spans if span.text.strip()
            )
            if joined.strip():
                return joined
        return mention.raw_text

    def _aspect_hypothesis_evidence_text(
        self,
        aspect: AspectOpinionHypothesis,
        mention: Any,
    ) -> str:
        if aspect.evidence_spans:
            joined = " ".join(
                span.text for span in aspect.evidence_spans if span.text.strip()
            )
            if joined.strip():
                return joined
        return mention.raw_text

    def _large_group_corroboration_counts(
        self,
        *,
        evidence_texts: list[str],
        hypotheses: Sequence[IssueSignalHypothesis | AspectOpinionHypothesis],
    ) -> dict[int, int]:
        normalized_counts: dict[str, int] = defaultdict(int)
        normalized_texts: list[str] = []
        for text in evidence_texts:
            normalized = normalize_alias(text) or text.casefold().strip()
            normalized_texts.append(normalized)
            normalized_counts[normalized] += 1
        return {
            id(hypothesis): max(1, normalized_counts[normalized_texts[index]])
            for index, hypothesis in enumerate(hypotheses)
        }

    # ------------------------------------------------------------------
    # Severity helpers
    # ------------------------------------------------------------------

    def _bump_issue_severity(
        self,
        severity: str,
        corroboration_count: int,
        evidence_mode: EvidenceMode,
    ) -> str:
        if evidence_mode in {
            EvidenceMode.QUESTION_OR_UNCERTAINTY,
            EvidenceMode.HEARSAY_OR_RUMOR,
        }:
            return "low"
        if corroboration_count <= 1:
            return (
                severity
                if severity in {"low", "medium", "high", "critical_like_proxy"}
                else "low"
            )
        if severity == "low":
            return "medium"
        if severity == "medium" and corroboration_count >= 3:
            return "high"
        return (
            severity
            if severity in {"low", "medium", "high", "critical_like_proxy"}
            else "low"
        )

    # ------------------------------------------------------------------
    # Routing and sentiment helpers
    # ------------------------------------------------------------------

    def _semantic_routing_mode(self, mention: Any) -> str:
        if getattr(mention, "semantic_route_hint", None) == "semantic_lite":
            return "semantic_lite"
        text_quality = getattr(mention, "text_quality_label", "normal")
        if text_quality in {
            "reaction_only",
            "low_information",
            "spam_like",
            "duplicate_like",
        }:
            return "semantic_lite"
        return "semantic_full"

    def _sentiment_label(self, score: float) -> SentimentValue:
        if score >= 0.35:
            return "positive"
        if score <= -0.35:
            return "negative"
        if abs(score) < 0.15:
            return "neutral"
        return "mixed"

    def _merge_sentiment_labels(self, labels: Sequence[str]) -> SentimentValue:
        label_set = set(labels)
        if {"positive", "negative"} <= label_set or "mixed" in label_set:
            return "mixed"
        if "positive" in label_set:
            return "positive"
        if "negative" in label_set:
            return "negative"
        return "neutral"

    def _merge_evidence_scope(self, scopes: list[EvidenceScope]) -> EvidenceScope:
        if EvidenceScope.LOCAL in scopes:
            return EvidenceScope.LOCAL
        if EvidenceScope.INHERITED in scopes:
            return EvidenceScope.INHERITED
        return EvidenceScope.AMBIGUOUS

    # ------------------------------------------------------------------
    # Fact builders
    # ------------------------------------------------------------------

    def _build_mention_sentiment_fact(
        self,
        hypothesis: MentionSentimentHypothesis,
        mention: Any,
    ) -> SentimentFact:
        return SentimentFact(
            mention_id=mention.mention_id,
            source_uap_id=mention.source_uap_id,
            sentiment=hypothesis.sentiment,  # type: ignore[arg-type]
            score=hypothesis.score,
            confidence=hypothesis.confidence,
            semantic_routing=hypothesis.semantic_routing,  # type: ignore[arg-type]
            sentiment_confidence=hypothesis.confidence,
            corroboration_confidence=hypothesis.corroboration_confidence,
            evidence_spans=hypothesis.evidence_spans,
            uncertainty_flags=hypothesis.uncertainty_flags,
            score_components=hypothesis.score_components,
            segment_ids=hypothesis.segment_ids,
            provenance=FactProvenance(
                source_uap_id=mention.source_uap_id,
                mention_id=mention.mention_id,
                provider_version=self.provider_version,
                rule_version="semantic-sentiment-v2",
                evidence_text=mention.raw_text,
            ),
        )

    def _build_target_sentiment_fact(
        self,
        hypothesis: TargetSentimentHypothesis,
        mention: Any,
    ) -> TargetSentimentFact:
        return TargetSentimentFact(
            mention_id=mention.mention_id,
            source_uap_id=mention.source_uap_id,
            target_key=hypothesis.target.target_key,
            target_text=hypothesis.target.target_text,
            canonical_entity_id=hypothesis.target.canonical_entity_id,
            concept_entity_id=hypothesis.target.concept_entity_id,
            unresolved_cluster_id=hypothesis.target.unresolved_cluster_id,
            target_kind=hypothesis.target.target_kind,  # type: ignore[arg-type]
            entity_type=hypothesis.target.entity_type,
            sentiment=hypothesis.sentiment,  # type: ignore[arg-type]
            score=hypothesis.score,
            confidence=hypothesis.confidence,
            semantic_routing=hypothesis.semantic_routing,  # type: ignore[arg-type]
            sentiment_confidence=hypothesis.confidence,
            target_grounding_confidence=hypothesis.target_grounding_confidence,
            corroboration_confidence=hypothesis.corroboration_confidence,
            target_inherited=hypothesis.target.inherited,
            inherited_from_mention_id=hypothesis.target.inherited_from_mention_id,
            evidence_scope=hypothesis.evidence_scope,
            evidence_spans=hypothesis.evidence_spans,
            uncertainty_flags=hypothesis.uncertainty_flags,
            score_components=hypothesis.score_components,
            segment_ids=hypothesis.segment_ids,
            provenance=FactProvenance(
                source_uap_id=mention.source_uap_id,
                mention_id=mention.mention_id,
                provider_version=self.provider_version,
                rule_version="semantic-target-sentiment-v2",
                evidence_text=mention.raw_text,
            ),
        )

    def _build_aspect_fact(
        self,
        hypothesis: AspectOpinionHypothesis,
        mention: Any,
    ) -> AspectOpinionFact:
        opinion_text = mention.raw_text
        if hypothesis.evidence_spans:
            start = min(span.start for span in hypothesis.evidence_spans)
            end = max(span.end for span in hypothesis.evidence_spans)
            opinion_text = mention.raw_text[start:end]
        return AspectOpinionFact(
            mention_id=mention.mention_id,
            source_uap_id=mention.source_uap_id,
            aspect=hypothesis.aspect,
            opinion_text=opinion_text,
            sentiment=hypothesis.sentiment,
            confidence=hypothesis.confidence,
            target_key=hypothesis.target.target_key if hypothesis.target else None,
            canonical_entity_id=hypothesis.target.canonical_entity_id
            if hypothesis.target
            else None,
            concept_entity_id=hypothesis.target.concept_entity_id
            if hypothesis.target
            else None,
            unresolved_cluster_id=hypothesis.target.unresolved_cluster_id
            if hypothesis.target
            else None,
            target_kind=(
                hypothesis.target.target_kind if hypothesis.target else "surface"
            ),  # type: ignore[arg-type]
            semantic_routing=hypothesis.semantic_routing,  # type: ignore[arg-type]
            sentiment_confidence=hypothesis.confidence,
            target_grounding_confidence=hypothesis.target_grounding_confidence,
            corroboration_confidence=hypothesis.corroboration_confidence,
            target_inherited=hypothesis.target.inherited
            if hypothesis.target
            else False,
            inherited_from_mention_id=hypothesis.target.inherited_from_mention_id
            if hypothesis.target
            else None,
            evidence_scope=hypothesis.evidence_scope,
            evidence_spans=hypothesis.evidence_spans,
            uncertainty_flags=hypothesis.uncertainty_flags,
            score_components=hypothesis.score_components,
            segment_id=hypothesis.segment_id,
            provenance=FactProvenance(
                source_uap_id=mention.source_uap_id,
                mention_id=mention.mention_id,
                provider_version=self.provider_version,
                rule_version="semantic-aspect-opinion-v2",
                evidence_text=mention.raw_text,
            ),
        )

    def _build_issue_fact(
        self,
        hypothesis: IssueSignalHypothesis,
        mention: Any,
    ) -> IssueSignalFact:
        return IssueSignalFact(
            mention_id=mention.mention_id,
            source_uap_id=mention.source_uap_id,
            issue_category=hypothesis.issue_category,
            severity=hypothesis.severity,  # type: ignore[arg-type]
            confidence=hypothesis.confidence,
            evidence_mode=hypothesis.evidence_mode,
            target_key=hypothesis.target.target_key if hypothesis.target else None,
            canonical_entity_id=hypothesis.target.canonical_entity_id
            if hypothesis.target
            else None,
            concept_entity_id=hypothesis.target.concept_entity_id
            if hypothesis.target
            else None,
            unresolved_cluster_id=hypothesis.target.unresolved_cluster_id
            if hypothesis.target
            else None,
            target_kind=(
                hypothesis.target.target_kind if hypothesis.target else "surface"
            ),  # type: ignore[arg-type]
            semantic_routing=hypothesis.semantic_routing,  # type: ignore[arg-type]
            issue_evidence_confidence=hypothesis.confidence,
            target_grounding_confidence=hypothesis.target_grounding_confidence,
            corroboration_confidence=hypothesis.corroboration_confidence,
            target_inherited=hypothesis.target.inherited
            if hypothesis.target
            else False,
            inherited_from_mention_id=hypothesis.target.inherited_from_mention_id
            if hypothesis.target
            else None,
            evidence_scope=hypothesis.evidence_scope,
            evidence_spans=hypothesis.evidence_spans,
            uncertainty_flags=hypothesis.uncertainty_flags,
            score_components=hypothesis.score_components,
            corroboration_count=hypothesis.corroboration_count,
            segment_id=hypothesis.segment_id,
            provenance=FactProvenance(
                source_uap_id=mention.source_uap_id,
                mention_id=mention.mention_id,
                provider_version=self.provider_version,
                rule_version="semantic-issue-signal-v2",
                evidence_text=mention.raw_text,
            ),
        )

"""EnricherService + inline ports of simple enrichers.

Inline ports (no separate files, short enough to keep here):
  - KeywordEnricher
  - StanceEnricher
  - IntentEnricher
  - SourceInfluenceEnricher

EnricherService orchestrates all enrichers following service.py logic.

Field mappings vs core-analysis:
  - mention.keywords → [] (field doesn't exist in MentionRecord)
  - mention.reply_count → 0 (field doesn't exist)
  - mention.platform → str directly (not an enum, no .value)

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from internal.enrichment.type import (
    EnrichmentBundle,
    FactProvenance,
    IntentFact,
    KeywordFact,
    SourceInfluenceFact,
    StanceFact,
)
from internal.enrichment.usecase.entity_enricher import SimplifiedEntityEnricher
from internal.enrichment.usecase.semantic_enricher import (
    SimplifiedSemanticInferenceEnricher,
)
from internal.enrichment.usecase.topic_enricher import SimplifiedTopicCandidateEnricher

# ---------------------------------------------------------------------------
# KeywordEnricher (ported from core-analysis keyword.py)
# ---------------------------------------------------------------------------

_KEYWORD_STOPWORDS = frozenset(
    {
        "và",
        "là",
        "của",
        "cho",
        "the",
        "and",
        "with",
        "that",
        "this",
        "mấy",
        "bác",
    }
)


class KeywordEnricher:
    name = "keyword"

    def enrich(
        self,
        mention: Any,  # MentionRecord
        context: Any,  # MentionContext | None
    ) -> list[KeywordFact]:
        tokens = [
            token
            for token in mention.normalized_text_compact.split()
            if len(token) > 2 and token not in _KEYWORD_STOPWORDS and token != "url"
        ]
        token_counts = Counter(tokens)
        keyphrases: list[str] = [token for token, _ in token_counts.most_common(3)]
        keyphrases.extend(mention.hashtags[:3])
        # mention.keywords doesn't exist in MentionRecord — skip
        deduped: list[str] = []
        for keyphrase in keyphrases:
            value = keyphrase.strip().lower()
            if value and value not in deduped:
                deduped.append(value)
        evidence = context.context_text if context is not None else mention.raw_text
        return [
            KeywordFact(
                mention_id=mention.mention_id,
                source_uap_id=mention.source_uap_id,
                keyphrase=kp,
                confidence=0.42,
                provenance=FactProvenance(
                    source_uap_id=mention.source_uap_id,
                    mention_id=mention.mention_id,
                    provider_version="keyword-rules-v1",
                    rule_version="keyword-rules-v1",
                    evidence_text=evidence,
                ),
            )
            for kp in deduped[:5]
        ]


# ---------------------------------------------------------------------------
# StanceEnricher (ported from core-analysis stance.py)
# ---------------------------------------------------------------------------


class StanceEnricher:
    name = "stance"

    def enrich(
        self,
        mention: Any,
        context: Any,
    ) -> list[StanceFact]:
        text = mention.normalized_text
        if "?" in mention.raw_text or any(
            token in text for token in ("hỏi", "sao", "why", "what")
        ):
            stance = "question"
            confidence = 0.8
        elif any(token in text for token in ("không", "lỗi", "bad", "hate", "chậm")):
            stance = "oppose"
            confidence = 0.65
        elif any(token in text for token in ("đẹp", "tốt", "love", "good", "tự hào")):
            stance = "support"
            confidence = 0.65
        else:
            stance = "neutral"
            confidence = 0.45
        evidence = context.context_text if context is not None else mention.raw_text
        return [
            StanceFact(
                mention_id=mention.mention_id,
                source_uap_id=mention.source_uap_id,
                stance=stance,  # type: ignore[arg-type]
                confidence=confidence,
                provenance=FactProvenance(
                    source_uap_id=mention.source_uap_id,
                    mention_id=mention.mention_id,
                    provider_version="stance-rules-v1",
                    rule_version="stance-rules-v1",
                    evidence_text=evidence,
                ),
            )
        ]


# ---------------------------------------------------------------------------
# IntentEnricher (ported from core-analysis intent.py)
# ---------------------------------------------------------------------------


class IntentEnricher:
    name = "intent"

    def enrich(
        self,
        mention: Any,
        context: Any,
    ) -> list[IntentFact]:
        text = mention.normalized_text
        if "?" in mention.raw_text or "hỏi" in text:
            intent = "question"
            confidence = 0.85
        elif any(token in text for token in ("mua", "đặt", "giá", "buy")):
            intent = "purchase_intent"
            confidence = 0.7
        elif any(token in text for token in ("đẹp", "tốt", "love", "chúc mừng")):
            intent = "praise"
            confidence = 0.7
        elif any(token in text for token in ("lỗi", "chậm", "bad", "không")):
            intent = "complaint"
            confidence = 0.65
        elif any(token in text for token in ("so với", "compare", "hơn")):
            intent = "compare"
            confidence = 0.6
        else:
            intent = "commentary"
            confidence = 0.4
        evidence = context.context_text if context is not None else mention.raw_text
        return [
            IntentFact(
                mention_id=mention.mention_id,
                source_uap_id=mention.source_uap_id,
                intent=intent,
                confidence=confidence,
                provenance=FactProvenance(
                    source_uap_id=mention.source_uap_id,
                    mention_id=mention.mention_id,
                    provider_version="intent-rules-v1",
                    rule_version="intent-rules-v1",
                    evidence_text=evidence,
                ),
            )
        ]


# ---------------------------------------------------------------------------
# SourceInfluenceEnricher (ported from core-analysis source.py)
# ---------------------------------------------------------------------------


class SourceInfluenceEnricher:
    name = "source_influence"

    def enrich(
        self,
        mention: Any,
        context: Any,
    ) -> list[SourceInfluenceFact]:
        engagement_score = float(
            (mention.likes or 0)
            + (mention.comments_count or 0)
            + 0  # mention.reply_count doesn't exist — use 0
            + (mention.shares or 0)
            + ((mention.views or 0) / 100.0)
        )
        if engagement_score >= 500:
            tier = "macro"
        elif engagement_score >= 100:
            tier = "mid"
        elif engagement_score >= 20:
            tier = "micro"
        else:
            tier = "nano"
        # mention.platform is a str directly (not an enum), so no .value
        channel = mention.platform
        evidence = context.context_text if context is not None else mention.raw_text
        return [
            SourceInfluenceFact(
                mention_id=mention.mention_id,
                source_uap_id=mention.source_uap_id,
                author_id=mention.author_id,
                channel=channel,
                influence_tier=tier,  # type: ignore[arg-type]
                engagement_score=round(engagement_score, 3),
                confidence=0.7,
                provenance=FactProvenance(
                    source_uap_id=mention.source_uap_id,
                    mention_id=mention.mention_id,
                    provider_version="source-influence-v1",
                    rule_version="source-influence-v1",
                    evidence_text=evidence,
                ),
            )
        ]


# ---------------------------------------------------------------------------
# EnricherService (ported from core-analysis service.py)
# ---------------------------------------------------------------------------


class EnricherService:
    """Orchestrates all enrichers for a batch of mentions.

    Mirrors core-analysis EnricherService.enrich_mentions() logic.
    """

    def __init__(
        self,
        entity_enricher: SimplifiedEntityEnricher | None = None,
        *,
        topic_enricher: SimplifiedTopicCandidateEnricher | None = None,
        semantic_enricher: SimplifiedSemanticInferenceEnricher | None = None,
    ) -> None:
        self.entity_enricher = entity_enricher or SimplifiedEntityEnricher()
        self.keyword_enricher = KeywordEnricher()
        self.topic_enricher = topic_enricher or SimplifiedTopicCandidateEnricher()
        self.semantic_enricher = (
            semantic_enricher or SimplifiedSemanticInferenceEnricher()
        )
        self.stance_enricher = StanceEnricher()
        self.intent_enricher = IntentEnricher()
        self.source_enricher = SourceInfluenceEnricher()

    def enrich_mentions(
        self,
        mentions: list[Any],  # list[MentionRecord]
        contexts: list[Any],  # list[MentionContext]
    ) -> EnrichmentBundle:
        context_map = {context.mention_id: context for context in contexts}
        bundle = EnrichmentBundle()

        # Step 1: entity extraction (prepare scans all mentions)
        self.entity_enricher.prepare(mentions, contexts)
        for mention in mentions:
            context = context_map.get(mention.mention_id)
            bundle.entity_facts.extend(self.entity_enricher.enrich(mention, context))
            bundle.stance_facts.extend(self.stance_enricher.enrich(mention, context))
            bundle.intent_facts.extend(self.intent_enricher.enrich(mention, context))
            bundle.source_influence_facts.extend(
                self.source_enricher.enrich(mention, context)
            )

        # Step 2: batch-local cluster annotation
        bundle.entity_facts, bundle.entity_candidate_clusters = (
            self.entity_enricher.annotate_batch_local_candidates(
                bundle.entity_facts, mentions
            )
        )

        # Step 3: keywords
        for mention in mentions:
            context = context_map.get(mention.mention_id)
            bundle.keyword_facts.extend(self.keyword_enricher.enrich(mention, context))

        # Step 4: semantic inference
        semantic_result = self.semantic_enricher.enrich(
            mentions,
            contexts,
            bundle.entity_facts,
        )
        bundle.sentiment_facts.extend(semantic_result.mention_sentiments)
        bundle.target_sentiment_facts.extend(semantic_result.target_sentiments)
        bundle.aspect_opinion_facts.extend(semantic_result.aspect_opinions)
        bundle.issue_signal_facts.extend(semantic_result.issue_signals)

        # Step 5: topic enrichment
        self.topic_enricher.prepare(
            mentions,
            contexts,
            entity_facts=bundle.entity_facts,
            aspect_facts=bundle.aspect_opinion_facts,
            issue_facts=bundle.issue_signal_facts,
        )
        for mention in mentions:
            context = context_map.get(mention.mention_id)
            bundle.topic_facts.extend(self.topic_enricher.enrich(mention, context))
        bundle.topic_artifacts.extend(self.topic_enricher.artifacts())

        return bundle

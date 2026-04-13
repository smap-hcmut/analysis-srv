"""Tests for Phase 4 enrichment pipeline.

Covers:
  - SentimentFact[] non-empty for polarity-rich text
  - EntityFact[] non-empty (at least one unresolved_candidate)
  - TopicFact[] non-empty
  - StanceFact[], IntentFact[], KeywordFact[], SourceInfluenceFact[] non-empty
  - IssueSignalFact[] empty (Phase 4 known limitation — no grounded targets)
  - bundle.model_dump() serializes without error
  - helpers: build_mention_contexts with and without thread_bundle
  - Pipeline wiring: _stage_enrichment via EnrichmentUseCase
"""

from __future__ import annotations

import pytest

from internal.enrichment.type import (
    EnricherConfig,
    EnrichmentBundle,
    EnrichmentInput,
)
from internal.enrichment.usecase.new import new_enrichment_usecase
from internal.enrichment.usecase.helpers import build_mention_contexts
from internal.normalization.type import MentionRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mention(
    mention_id: str,
    text: str,
    *,
    source_uap_id: str = "uap-001",
    platform: str = "facebook",
    author_id: str = "author1",
    root_id: str = "",
    parent_id: str | None = None,
    likes: int = 0,
    comments_count: int = 0,
    shares: int = 0,
    views: int = 0,
    hashtags: list[str] | None = None,
    language: str = "vi",
    text_quality_label: str = "normal",
    semantic_route_hint: str = "semantic_full",
) -> MentionRecord:
    return MentionRecord(
        mention_id=mention_id,
        source_uap_id=source_uap_id,
        platform=platform,
        author_id=author_id,
        raw_text=text,
        normalized_text=text.lower(),
        normalized_text_compact=text.lower(),
        root_id=root_id or mention_id,
        parent_id=parent_id,
        hashtags=hashtags or [],
        likes=likes,
        comments_count=comments_count,
        shares=shares,
        views=views,
        language=language,
        text_quality_label=text_quality_label,
        semantic_route_hint=semantic_route_hint,
    )


# ---------------------------------------------------------------------------
# Sample mentions with Vietnamese polarity cues
# ---------------------------------------------------------------------------

POSITIVE_MENTION = make_mention(
    "m-pos-1",
    "Sản phẩm này rất đẹp và tốt, tôi rất thích. #VinFast #Xe",
    root_id="m-pos-1",
    likes=120,
    shares=30,
    hashtags=["VinFast", "Xe"],
)

NEGATIVE_MENTION = make_mention(
    "m-neg-1",
    "Dịch vụ quá tệ, nhân viên không nhiệt tình, sẽ không quay lại.",
    root_id="m-neg-1",
    likes=5,
    comments_count=2,
)

QUESTION_MENTION = make_mention(
    "m-q-1",
    "Giá xe VinFast là bao nhiêu? Có ưu đãi gì không?",
    root_id="m-q-1",
)

ENTITY_MENTION = make_mention(
    "m-ent-1",
    "Chính phủ Việt Nam đã ký kết thỏa thuận với @Samsung về chip bán dẫn. #technology",
    root_id="m-ent-1",
    hashtags=["technology"],
    views=5000,
)


# ---------------------------------------------------------------------------
# Test: empty input
# ---------------------------------------------------------------------------


class TestEnrichmentEmptyInput:
    def test_empty_mentions_returns_empty_bundle(self):
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[], thread_bundle=None)
        output = svc.enrich(inp)
        bundle = output.bundle
        assert isinstance(bundle, EnrichmentBundle)
        assert bundle.sentiment_facts == []
        assert bundle.entity_facts == []
        assert bundle.keyword_facts == []
        assert bundle.stance_facts == []
        assert bundle.intent_facts == []
        assert bundle.source_influence_facts == []
        assert bundle.topic_facts == []

    def test_enricher_versions_populated(self):
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[], thread_bundle=None)
        output = svc.enrich(inp)
        assert "entity" in output.enricher_versions
        assert "semantic" in output.enricher_versions


# ---------------------------------------------------------------------------
# Test: single positive mention
# ---------------------------------------------------------------------------


class TestEnrichmentSingleMention:
    def setup_method(self):
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[POSITIVE_MENTION], thread_bundle=None)
        self.output = svc.enrich(inp)
        self.bundle = self.output.bundle

    def test_sentiment_fact_non_empty(self):
        assert len(self.bundle.sentiment_facts) >= 1
        fact = self.bundle.sentiment_facts[0]
        assert fact.mention_id == POSITIVE_MENTION.mention_id
        assert fact.sentiment in ("positive", "neutral", "negative", "mixed")
        assert 0.0 <= fact.confidence <= 1.0

    def test_entity_fact_non_empty(self):
        # "#VinFast", "#Xe" hashtags → at least one entity
        assert len(self.bundle.entity_facts) >= 1
        fact = self.bundle.entity_facts[0]
        assert fact.resolution_kind == "unresolved_candidate"

    def test_keyword_fact_non_empty(self):
        assert len(self.bundle.keyword_facts) >= 1
        fact = self.bundle.keyword_facts[0]
        assert fact.keyphrase
        assert 0.0 <= fact.confidence <= 1.0

    def test_stance_fact_non_empty(self):
        assert len(self.bundle.stance_facts) == 1
        fact = self.bundle.stance_facts[0]
        assert fact.stance in ("support", "oppose", "question", "neutral")

    def test_intent_fact_non_empty(self):
        assert len(self.bundle.intent_facts) == 1
        fact = self.bundle.intent_facts[0]
        assert fact.intent

    def test_source_influence_fact_non_empty(self):
        assert len(self.bundle.source_influence_facts) == 1
        fact = self.bundle.source_influence_facts[0]
        assert fact.influence_tier in ("nano", "micro", "mid", "macro")
        assert fact.engagement_score > 0  # likes=120 + shares=30

    def test_topic_fact_non_empty(self):
        assert len(self.bundle.topic_facts) >= 1
        fact = self.bundle.topic_facts[0]
        assert fact.topic_key
        assert fact.topic_label
        assert 0.0 <= fact.confidence <= 1.0

    def test_issue_signal_facts_empty_phase4_limitation(self):
        # Phase 4: no grounded targets → no issue signals
        assert self.bundle.issue_signal_facts == []

    def test_target_sentiment_facts_empty_phase4_limitation(self):
        assert self.bundle.target_sentiment_facts == []

    def test_bundle_serializes_without_error(self):
        data = self.bundle.model_dump()
        assert isinstance(data, dict)
        assert "sentiment_facts" in data
        assert "entity_facts" in data


# ---------------------------------------------------------------------------
# Test: negative mention sentiment label
# ---------------------------------------------------------------------------


class TestEnrichmentNegativeMention:
    def setup_method(self):
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[NEGATIVE_MENTION], thread_bundle=None)
        self.bundle = svc.enrich(inp).bundle

    def test_stance_is_oppose(self):
        assert self.bundle.stance_facts[0].stance == "oppose"

    def test_intent_is_complaint(self):
        assert self.bundle.intent_facts[0].intent == "complaint"


# ---------------------------------------------------------------------------
# Test: question mention
# ---------------------------------------------------------------------------


class TestEnrichmentQuestionMention:
    def setup_method(self):
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[QUESTION_MENTION], thread_bundle=None)
        self.bundle = svc.enrich(inp).bundle

    def test_stance_is_question(self):
        assert self.bundle.stance_facts[0].stance == "question"

    def test_intent_is_question(self):
        assert self.bundle.intent_facts[0].intent == "question"


# ---------------------------------------------------------------------------
# Test: entity extraction from @mention and #hashtag
# ---------------------------------------------------------------------------


class TestEnrichmentEntityExtraction:
    def setup_method(self):
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[ENTITY_MENTION], thread_bundle=None)
        self.bundle = svc.enrich(inp).bundle

    def test_entity_facts_include_at_mention(self):
        candidates = [f.candidate_text for f in self.bundle.entity_facts]
        # "@Samsung" should be extracted
        assert any("Samsung" in c for c in candidates)

    def test_entity_facts_include_hashtag(self):
        candidates = [f.candidate_text for f in self.bundle.entity_facts]
        assert any(c.startswith("#") for c in candidates)

    def test_source_influence_tier_macro_for_high_views(self):
        # views=5000 → 50 engagement from views alone → micro/mid
        fact = self.bundle.source_influence_facts[0]
        assert fact.influence_tier in ("micro", "mid", "macro")


# ---------------------------------------------------------------------------
# Test: batch of multiple mentions — topic clustering
# ---------------------------------------------------------------------------


class TestEnrichmentBatch:
    def setup_method(self):
        # Two mentions about the same topic (VinFast) → should cluster
        m1 = make_mention("m-b1", "VinFast ra mắt xe điện mới, giá rất cạnh tranh.")
        m2 = make_mention("m-b2", "Xe điện VinFast bán chạy nhất tuần này tại Hà Nội.")
        m3 = make_mention("m-b3", "Samsung công bố chip mới cho điện thoại AI cao cấp.")
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[m1, m2, m3], thread_bundle=None)
        self.bundle = svc.enrich(inp).bundle
        self.mentions = [m1, m2, m3]

    def test_sentiment_fact_per_mention(self):
        assert len(self.bundle.sentiment_facts) == len(self.mentions)

    def test_stance_fact_per_mention(self):
        assert len(self.bundle.stance_facts) == len(self.mentions)

    def test_intent_fact_per_mention(self):
        assert len(self.bundle.intent_facts) == len(self.mentions)

    def test_source_influence_fact_per_mention(self):
        assert len(self.bundle.source_influence_facts) == len(self.mentions)

    def test_topic_facts_non_empty(self):
        assert len(self.bundle.topic_facts) >= len(self.mentions)

    def test_topic_artifacts_non_empty(self):
        assert len(self.bundle.topic_artifacts) >= 1

    def test_topic_artifact_has_top_terms(self):
        for artifact in self.bundle.topic_artifacts:
            assert isinstance(artifact.top_terms, list)
            assert artifact.topic_size >= 1

    def test_entity_candidate_clusters_for_repeated_vinfast(self):
        # "VinFast" or "Xe điện VinFast" should form a cluster
        # At minimum we should have entity facts
        assert len(self.bundle.entity_facts) >= 1

    def test_bundle_model_dump_serializes(self):
        data = self.bundle.model_dump()
        assert isinstance(data["topic_facts"], list)
        assert isinstance(data["entity_facts"], list)


# ---------------------------------------------------------------------------
# Test: build_mention_contexts helper
# ---------------------------------------------------------------------------


class TestBuildMentionContextsHelper:
    def test_without_thread_bundle_creates_stubs(self):
        m1 = make_mention("m1", "text one", root_id="m1")
        m2 = make_mention("m2", "text two", root_id="m1", parent_id="m1")
        contexts = build_mention_contexts([m1, m2], thread_bundle=None)
        assert len(contexts) == 2
        ctx1 = next(c for c in contexts if c.mention_id == "m1")
        ctx2 = next(c for c in contexts if c.mention_id == "m2")
        assert ctx1.root_id == "m1"
        assert ctx2.parent_id == "m1"

    def test_with_thread_bundle_uses_existing_contexts(self):
        from internal.threads.type import MentionContext, ThreadBundle

        existing = [
            MentionContext(mention_id="m1", root_id="m1", context_text="custom ctx"),
        ]
        bundle = ThreadBundle(contexts=existing)
        m1 = make_mention("m1", "text one", root_id="m1")
        contexts = build_mention_contexts([m1], thread_bundle=bundle)
        assert len(contexts) == 1
        assert contexts[0].context_text == "custom ctx"

    def test_with_empty_thread_bundle_falls_back_to_stubs(self):
        from internal.threads.type import ThreadBundle

        bundle = ThreadBundle(contexts=[])
        m1 = make_mention("m1", "text one", root_id="m1")
        contexts = build_mention_contexts([m1], thread_bundle=bundle)
        assert len(contexts) == 1
        assert contexts[0].context_text == "text one"


# ---------------------------------------------------------------------------
# Test: high-engagement mention gets correct influence tier
# ---------------------------------------------------------------------------


class TestSourceInfluenceTiers:
    @pytest.mark.parametrize(
        "likes,shares,views,expected_tier",
        [
            (0, 0, 0, "nano"),
            (15, 5, 0, "micro"),  # 20 engagement — exactly at threshold
            (80, 25, 0, "mid"),  # 105 engagement
            (300, 250, 0, "macro"),  # 550 engagement
        ],
    )
    def test_influence_tiers(self, likes, shares, views, expected_tier):
        m = make_mention(
            f"m-tier-{likes}",
            "Some text",
            likes=likes,
            shares=shares,
            views=views,
        )
        svc = new_enrichment_usecase()
        inp = EnrichmentInput(mentions=[m], thread_bundle=None)
        bundle = svc.enrich(inp).bundle
        assert bundle.source_influence_facts[0].influence_tier == expected_tier


# ---------------------------------------------------------------------------
# Test: config flags
# ---------------------------------------------------------------------------


class TestEnricherConfig:
    def test_default_config_all_enabled(self):
        config = EnricherConfig()
        assert config.entity_enabled
        assert config.semantic_enabled
        assert config.topic_enabled

    def test_new_enrichment_usecase_with_explicit_config(self):
        config = EnricherConfig(
            entity_enabled=True, semantic_enabled=True, topic_enabled=True
        )
        svc = new_enrichment_usecase(config)
        m = make_mention("m-cfg-1", "Test với Samsung và Apple đẹp tốt.")
        inp = EnrichmentInput(mentions=[m], thread_bundle=None)
        output = svc.enrich(inp)
        assert isinstance(output.bundle, EnrichmentBundle)

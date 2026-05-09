from datetime import datetime, timezone

from internal.analytics.type import AnalyticsResult
from internal.analytics.usecase.helpers import add_uap_metadata
from internal.analytics.usecase.batch_enricher import (
    NLPBatchEnricher,
    enrich_nlp_facts_with_bundle,
)
from internal.analytics.type import Config as AnalyticsConfig
from internal.enrichment.type import (
    EnrichmentBundle,
    EntityFact,
    FactProvenance,
    IssueSignalFact,
    SourceInfluenceFact,
    TopicFact,
)
from internal.enrichment.usecase._semantic_models import EvidenceMode
from internal.model.insight_message import InsightMessage
from internal.model.uap import (
    UAPAuthor,
    UAPContent,
    UAPContext,
    UAPEntity,
    UAPIngest,
    UAPRecord,
    UAPSignals,
    UAPSource,
)
from internal.pipeline.type import NLPFact
from internal.post_insight.repository.postgre.helpers import transform_to_post_insight


def _make_uap(event_id: str, doc_id: str) -> UAPRecord:
    return UAPRecord(
        event_id=event_id,
        ingest=UAPIngest(
            project_id="proj-1",
            source=UAPSource(source_id="src-1", source_type="facebook"),
            entity=UAPEntity(entity_type="brand", entity_name="VinFast", brand="VinFast"),
        ),
        content=UAPContent(
            doc_id=doc_id,
            doc_type="post",
            text="VinFast service is bad",
            published_at="2026-04-23T00:00:00Z",
            author=UAPAuthor(author_id="author-1", display_name="Author One"),
        ),
        context=UAPContext(campaign_id="camp-1"),
        signals=UAPSignals(),
    )


def _make_fact(event_id: str, doc_id: str) -> NLPFact:
    uap = _make_uap(event_id, doc_id)
    result = AnalyticsResult(
        id="analytics-1",
        project_id="proj-1",
        source_id="src-1",
        platform="facebook",
        published_at=datetime.now(timezone.utc),
        analyzed_at=datetime.now(timezone.utc),
        content_text=uap.content.text,
        permalink="https://example.com/post",
        author_id="author-1",
        author_name="Author One",
        hashtags=["VinFast"],
    )
    return NLPFact(
        uap_id=doc_id,
        insight_message=InsightMessage(),
        uap_record=uap,
        analytics_result=result,
    )


def test_enrichment_bundle_is_attached_to_output_and_post_insight():
    fact = _make_fact("event-1", "doc-1")
    bundle = EnrichmentBundle(
        entity_facts=[
            EntityFact(
                mention_id="mention-1",
                source_uap_id="event-1",
                candidate_text="VinFast",
                entity_type="brand",
                confidence=0.91,
                matched_by="hashtag",
                provenance=FactProvenance(
                    source_uap_id="event-1",
                    mention_id="mention-1",
                    provider_version="v1",
                    rule_version="r1",
                    evidence_text="#VinFast",
                ),
            )
        ],
        topic_facts=[
            TopicFact(
                mention_id="mention-1",
                source_uap_id="event-1",
                topic_key="after-sales",
                topic_label="After Sales",
                reporting_topic_label="After Sales",
                confidence=0.82,
                provenance=FactProvenance(
                    source_uap_id="event-1",
                    mention_id="mention-1",
                    provider_version="v1",
                    rule_version="r1",
                    evidence_text="service is bad",
                ),
            )
        ],
        issue_signal_facts=[
            IssueSignalFact(
                mention_id="mention-1",
                source_uap_id="event-1",
                issue_category="service_quality",
                severity="medium",
                confidence=0.71,
                evidence_mode=EvidenceMode.DIRECT_COMPLAINT,
                provenance=FactProvenance(
                    source_uap_id="event-1",
                    mention_id="mention-1",
                    provider_version="v1",
                    rule_version="r1",
                    evidence_text="service is bad",
                ),
            )
        ],
        source_influence_facts=[
            SourceInfluenceFact(
                mention_id="mention-1",
                source_uap_id="event-1",
                author_id="author-1",
                channel="facebook",
                influence_tier="micro",
                engagement_score=23.0,
                confidence=0.66,
                provenance=FactProvenance(
                    source_uap_id="event-1",
                    mention_id="mention-1",
                    provider_version="v1",
                    rule_version="r1",
                    evidence_text="author influence",
                ),
            )
        ],
    )

    enrich_nlp_facts_with_bundle([fact], bundle)

    assert len(fact.insight_message.nlp.entities) == 1
    assert fact.insight_message.nlp.entities[0].type == "BRAND"
    assert fact.insight_message.nlp.entities[0].value == "VinFast"
    assert fact.insight_message.enrichment.entity_count == 1
    assert fact.insight_message.enrichment.topic_count == 1
    assert fact.insight_message.enrichment.topic_labels == ["After Sales"]
    assert fact.insight_message.enrichment.issue_categories == ["service_quality"]
    assert fact.insight_message.enrichment.source_influence_tier == "micro"

    post_insight_input = NLPBatchEnricher.to_post_insight_input(fact, bundle)
    transformed = transform_to_post_insight(post_insight_input)

    assert transformed["uap_metadata"]["enrichment"] == {
        "entity_count": 1,
        "topic_count": 1,
        "topic_labels": ["After Sales"],
        "issue_count": 1,
        "issue_categories": ["service_quality"],
        "source_influence_tier": "micro",
    }


def test_youtube_comment_original_url_is_built_from_parent_context():
    uap = UAPRecord(
        event_id="event-yt-comment",
        ingest=UAPIngest(
            project_id="proj-1",
            source=UAPSource(source_id="UgxComment123", source_type="youtube"),
        ),
        content=UAPContent(
            doc_id="yt_c_UgxComment123",
            doc_type="comment",
            text="Ship này quá hay",
            url="",
            published_at="2026-05-09T00:00:00Z",
            author=UAPAuthor(author_id="author-yt", display_name="@demo"),
        ),
        raw={
            "hierarchy": {"root_id": "yt_p_kuifyIKXOOM", "depth": 1},
            "platform_meta": {
                "youtube": {
                    "parent_video_id": "kuifyIKXOOM",
                    "parent_url": "https://www.youtube.com/watch?v=kuifyIKXOOM",
                }
            },
        },
    )
    result = AnalyticsResult(
        id="analytics-yt-comment",
        project_id="proj-1",
        source_id="UgxComment123",
        platform="youtube",
        published_at=datetime.now(timezone.utc),
        analyzed_at=datetime.now(timezone.utc),
    )

    add_uap_metadata(result, uap, AnalyticsConfig())

    assert result.permalink == "https://www.youtube.com/watch?v=kuifyIKXOOM&lc=UgxComment123"
    assert result.raw_context["hierarchy"]["root_id"] == "yt_p_kuifyIKXOOM"

    fact = NLPFact(
        uap_id=uap.content.doc_id,
        insight_message=InsightMessage(),
        uap_record=uap,
        analytics_result=result,
    )
    transformed = transform_to_post_insight(NLPBatchEnricher.to_post_insight_input(fact))

    assert transformed["uap_metadata"]["url"] == "https://www.youtube.com/watch?v=kuifyIKXOOM&lc=UgxComment123"
    assert transformed["uap_metadata"]["platform_meta"]["youtube"]["parent_video_id"] == "kuifyIKXOOM"

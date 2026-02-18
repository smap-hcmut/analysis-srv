import uuid
from typing import Optional

from pkg.logger.logger import Logger
from internal.model.uap import UAPRecord
from internal.model.insight_message import (
    InsightMessage,
    Project,
    Identity,
    Author as EnrichedAuthor,
    Content,
    NLP,
    NLPSentiment,
    NLPAspect,
    Business,
    BusinessImpact,
    BusinessEngagement,
    BusinessAlert,
    RAG,
    RAGIndex,
    RAGQualityGate,
    RAGCitation,
    RAGVectorRef,
    Provenance,
    ProvenanceStep,
)
from internal.analytics.type import AnalyticsResult
from ..type import BuildInput, BuildOutput
from ..constant import (
    ENRICHED_VERSION,
    CITATION_SNIPPET_MAX_LENGTH,
    RAG_MIN_TEXT_LENGTH,
)
from .helpers import (
    build_snippet,
    confidence_label,
    determine_priority,
    safe_iso_now,
)


def process(input_data: BuildInput, logger: Logger) -> BuildOutput:
    try:
        uap = input_data.uap_record
        result = input_data.analytics_result

        enriched = InsightMessage(
            message_version=ENRICHED_VERSION,
            event_id=uap.event_id or f"analytics_{uuid.uuid4()}",
            project=_build_project(uap),
            identity=_build_identity(uap),
            content=_build_content(uap, result),
            nlp=_build_nlp(result),
            business=_build_business(uap, result),
            rag=_build_rag(uap, result),
            provenance=_build_provenance(uap, result),
        )

        return BuildOutput(enriched=enriched, success=True)

    except Exception as exc:
        logger.error(f"internal.builder.usecase.process: Build failed: {exc}")
        return BuildOutput(
            enriched=InsightMessage(),
            success=False,
            error_message=str(exc),
        )


def _build_project(uap: UAPRecord) -> Project:
    return Project(
        project_id=uap.ingest.project_id,
        entity_type=uap.ingest.entity.entity_type,
        entity_name=uap.ingest.entity.entity_name,
        brand=uap.ingest.entity.brand,
        campaign_id=uap.context.campaign_id,
    )


def _build_identity(uap: UAPRecord) -> Identity:
    return Identity(
        source_type=uap.ingest.source.source_type,
        source_id=uap.ingest.source.source_id,
        doc_id=uap.content.doc_id,
        doc_type=uap.content.doc_type,
        url=uap.content.url,
        language=uap.content.language,
        published_at=uap.content.published_at,
        ingested_at=uap.ingest.batch.received_at,
        author=EnrichedAuthor(
            author_id=uap.content.author.author_id,
            display_name=uap.content.author.display_name,
            author_type=uap.content.author.author_type,
        ),
    )


def _build_content(uap: UAPRecord, result: AnalyticsResult) -> Content:
    return Content(
        text=uap.content.text,
        clean_text=result.content_text or uap.content.text,
        summary="",
    )


def _build_nlp(result: AnalyticsResult) -> NLP:
    # Sentiment
    sentiment = NLPSentiment(
        label=result.overall_sentiment,
        score=result.overall_sentiment_score,
        confidence=confidence_label(result.overall_confidence),
        explanation="",
    )

    # Aspects
    aspects = []
    if isinstance(result.aspects_breakdown, dict):
        for aspect_data in result.aspects_breakdown.get("aspects", []):
            if isinstance(aspect_data, dict):
                aspects.append(
                    NLPAspect(
                        aspect=aspect_data.get("aspect", ""),
                        polarity=aspect_data.get("polarity", "NEUTRAL"),
                        confidence=float(aspect_data.get("confidence", 0.0)),
                        evidence=aspect_data.get("evidence", ""),
                    )
                )

    # Entities
    entities = []

    return NLP(
        sentiment=sentiment,
        aspects=aspects,
        entities=entities,
    )


def _build_business(uap: UAPRecord, result: AnalyticsResult) -> Business:
    engagement = BusinessEngagement(
        like_count=uap.signals.engagement.like_count,
        comment_count=uap.signals.engagement.comment_count,
        share_count=uap.signals.engagement.share_count,
        view_count=uap.signals.engagement.view_count,
    )

    priority = determine_priority(result.impact_score)

    impact = BusinessImpact(
        engagement=engagement,
        impact_score=result.impact_score,
        priority=priority,
    )

    # Alerts
    alerts = []
    if result.risk_level in ("HIGH", "CRITICAL"):
        alerts.append(
            BusinessAlert(
                alert_type="NEGATIVE_BRAND_SIGNAL",
                severity=result.risk_level,
                reason=f"Post has {result.overall_sentiment} sentiment with {result.risk_level} risk level.",
                suggested_action="Review and monitor related discussions.",
            )
        )

    return Business(impact=impact, alerts=alerts)


def _build_rag(uap: UAPRecord, result: AnalyticsResult) -> RAG:
    text = uap.content.text
    has_aspects = bool(
        result.aspects_breakdown and result.aspects_breakdown.get("aspects")
    )
    is_not_spam = result.primary_intent not in ("SPAM", "SEEDING")

    quality_gate = RAGQualityGate(
        min_length_ok=len(text) >= RAG_MIN_TEXT_LENGTH,
        has_aspect=has_aspects,
        not_spam=is_not_spam,
    )

    should_index = quality_gate.min_length_ok and quality_gate.not_spam

    citation = RAGCitation(
        source=uap.ingest.source.source_type,
        title=f"{uap.ingest.source.source_type} {uap.content.doc_type.title()}",
        snippet=build_snippet(text, CITATION_SNIPPET_MAX_LENGTH),
        url=uap.content.url or "",
        published_at=uap.content.published_at or "",
    )

    vector_ref = RAGVectorRef(
        provider="qdrant",
        collection=uap.ingest.project_id,
        point_id=uap.event_id,
    )

    return RAG(
        index=RAGIndex(should_index=should_index, quality_gate=quality_gate),
        citation=citation,
        vector_ref=vector_ref,
    )


def _build_provenance(uap: UAPRecord, result: AnalyticsResult) -> Provenance:
    now = safe_iso_now()
    steps = [
        ProvenanceStep(step="normalize_uap", at=now),
    ]

    # AI model steps
    if result.overall_sentiment != "NEUTRAL" or result.overall_confidence > 0:
        steps.append(
            ProvenanceStep(
                step="sentiment_analysis",
                model=f"phobert-sentiment-v{result.model_version}",
            )
        )

    if result.aspects_breakdown:
        steps.append(
            ProvenanceStep(
                step="aspect_extraction",
                model=f"phobert-aspect-v{result.model_version}",
            )
        )

    if result.keywords:
        steps.append(
            ProvenanceStep(
                step="keyword_extraction",
                model="spacy-yake",
            )
        )

    return Provenance(
        raw_ref=uap.ingest.trace.raw_ref,
        pipeline=steps,
    )

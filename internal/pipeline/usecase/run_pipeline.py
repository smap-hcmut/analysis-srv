"""run_pipeline.py — main pipeline orchestrator.

Phase 3: normalization, dedup, spam, threads stages are wired with real
usecase implementations injected via PipelineConfig.services.
Enrichment / reporting stages remain stubs for Phases 4–5.
"""

import dataclasses
import time

from ..type import (
    IngestedBatchBundle,
    PipelineFacts,
    PipelineRunResult,
    PipelineConfig,
    StageResult,
)
from ..constant import (
    STAGE_NORMALIZATION,
    STAGE_DEDUP,
    STAGE_SPAM,
    STAGE_THREADS,
    STAGE_NLP,
    STAGE_ENRICHMENT,
    STAGE_REVIEW,
    STAGE_REPORTING,
    STAGE_CRISIS,
)
from .helpers import _run_stage, _collect_timings
from internal.runtime.type import RunContext
from internal.runtime.usecase.run_manifest import build_run_manifest
from internal.enrichment.type import EnrichmentInput, EnrichmentBundle
from internal.reporting.type import (
    ReportingInput,
    DedupClusterRecord as ReportingDedupClusterRecord,
    AuthorQualityRecord as ReportingAuthorQualityRecord,
)
from internal.threads.type import ThreadBundle
from internal.crisis.type import CrisisInput


# ---------------------------------------------------------------------------
# Conversion helpers — translate pipeline dataclasses to reporting Pydantic models
# ---------------------------------------------------------------------------


def _convert_dedup_clusters(raw: list) -> list[ReportingDedupClusterRecord]:
    """Convert dedup.type.DedupClusterRecord dataclasses → reporting Pydantic models.

    Field mapping:
      dedup_cluster_id → cluster_id
      dedup_kind       → cluster_kind
      representative_mention_id → representative_mention_id (unchanged)
      mention_ids               → mention_ids (unchanged)
    """
    result = []
    for rec in raw:
        result.append(
            ReportingDedupClusterRecord(
                cluster_id=rec.dedup_cluster_id,
                cluster_kind=rec.dedup_kind,
                representative_mention_id=rec.representative_mention_id,
                mention_ids=list(rec.mention_ids),
            )
        )
    return result


def _convert_author_quality(raw: list) -> list[ReportingAuthorQualityRecord]:
    """Convert spam.type.AuthorQualityRecord dataclasses → reporting Pydantic models.

    Field mapping:
      author_id              → author_id (unchanged)
      author_inorganic_score → inorganic_score
      author_suspicious      → quality_tier ("suspicious" | "normal")
      1 - author_inorganic_score → quality_score
    """
    result = []
    for rec in raw:
        result.append(
            ReportingAuthorQualityRecord(
                author_id=rec.author_id,
                inorganic_score=rec.author_inorganic_score,
                quality_tier="suspicious" if rec.author_suspicious else "normal",
                quality_score=max(0.0, 1.0 - rec.author_inorganic_score),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Stage implementations — Phase 3
# ---------------------------------------------------------------------------


def _stage_normalize(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Normalize raw UAPRecords into MentionRecords."""
    svc = config.services.normalization
    if svc is None:
        return facts
    norm_batch = svc.normalize(batch)
    return dataclasses.replace(
        facts,
        normalized_records=norm_batch.mentions,
        filtered_out_unsupported_language=norm_batch.filtered_out_unsupported_language,
    )


def _stage_dedup(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Annotate MentionRecords with MinHash dedup cluster info."""
    svc = config.services.dedup
    if svc is None or not facts.normalized_records:
        return facts
    updated, result = svc.annotate(facts.normalized_records)
    return dataclasses.replace(
        facts,
        normalized_records=updated,
        dedup_clusters=result.clusters,
    )


def _stage_spam(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Score mentions and authors for spam / inorganic signals."""
    svc = config.services.spam
    if svc is None or not facts.normalized_records:
        return facts
    updated, result = svc.annotate(facts.normalized_records)
    return dataclasses.replace(
        facts,
        normalized_records=updated,
        spam_scores=result.author_profiles,
    )


def _stage_threads(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Build thread bundles with lineage context for each root post."""
    svc = config.services.threads
    if svc is None or not facts.normalized_records:
        return facts
    bundle = svc.build(facts.normalized_records)
    return dataclasses.replace(facts, thread_bundles=[bundle])


def _stage_nlp(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """NLP enrichment stage — runs preprocessing, intent, keywords, sentiment, impact.

    Calls NLPBatchEnricher.enrich_batch() which mirrors the legacy AnalyticsProcess
    but is batch-oriented and fully synchronous (no async deps).
    """
    svc = config.services.nlp_enricher
    if svc is None:
        return facts
    records_for_nlp = batch.records
    if facts.normalized_records:
        allowed_ids = {
            m.source_uap_id
            for m in facts.normalized_records
            if getattr(m, "source_uap_id", None)
        }
        allowed_ids.update(
            m.origin_id for m in facts.normalized_records if getattr(m, "origin_id", None)
        )

        if allowed_ids:
            records_for_nlp = [
                r
                for r in batch.records
                if r.event_id in allowed_ids
                or (r.content is not None and r.content.doc_id in allowed_ids)
            ]

    nlp_facts = svc.enrich_batch(records_for_nlp, batch.project_id)
    return dataclasses.replace(
        facts,
        nlp_facts=nlp_facts,
        nlp_input_records=len(records_for_nlp),
    )


def _stage_enrichment(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Phase 4: NER, semantic inference, topic enrichment."""
    svc = config.services.enrichment
    if svc is None or not facts.normalized_records:
        return facts

    thread_bundle = facts.thread_bundles[0] if facts.thread_bundles else None
    inp = EnrichmentInput(
        mentions=facts.normalized_records,
        thread_bundle=thread_bundle,
    )
    output = svc.enrich(inp)
    return dataclasses.replace(facts, enrichment_bundle=output.bundle)


def _stage_reporting(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Phase 5: insight card generation and BI report bundle."""
    svc = config.services.reporting
    if svc is None or not facts.normalized_records:
        return facts

    thread_bundle = facts.thread_bundles[0] if facts.thread_bundles else ThreadBundle()
    enrichment = facts.enrichment_bundle
    if enrichment is None:
        enrichment = EnrichmentBundle()

    inp = ReportingInput(
        run_id=ctx.run_id,
        project_id=batch.project_id,
        campaign_id=batch.campaign_id,
        mentions=facts.normalized_records,
        thread_bundle=thread_bundle,
        enrichment_bundle=enrichment,
        ontology=config.services.ontology_registry,
        dedup_clusters=_convert_dedup_clusters(facts.dedup_clusters or []),
        author_quality=_convert_author_quality(facts.spam_scores or []),
    )
    output = svc.report(inp)
    return dataclasses.replace(
        facts,
        bi_bundle=output.bi_reports,
        insight_cards=output.bi_reports.insight_card_bundle.cards,
    )


def _stage_crisis(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Phase 6: rule-based crisis detection from BI report bundle."""
    svc = config.services.crisis
    if svc is None or facts.bi_bundle is None:
        return facts

    inp = CrisisInput(
        run_id=ctx.run_id,
        project_id=batch.project_id,
        campaign_id=batch.campaign_id,
        bi_reports=facts.bi_bundle,
    )
    output = svc.assess(inp)
    return dataclasses.replace(facts, crisis_assessment=output.assessment)


def _stage_review(
    facts: PipelineFacts,
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineFacts:
    """Phase 4+: enqueue low-confidence enrichment facts for human review."""
    svc = config.services.review
    if svc is None or facts.enrichment_bundle is None:
        return facts

    bundle = facts.enrichment_bundle
    # Enqueue entity facts below confidence threshold
    for fact in getattr(bundle, "entity_facts", []):
        try:
            svc.enqueue(
                run_id=ctx.run_id,
                project_id=batch.project_id,
                mention_id=getattr(fact, "mention_id", ""),
                fact_type="entity",
                fact_payload=fact.__dict__ if hasattr(fact, "__dict__") else {},
                confidence=float(getattr(fact, "confidence", 0.0)),
            )
        except Exception:
            pass  # ReviewQueueFullError or other — non-fatal

    # Enqueue topic facts below confidence threshold
    for fact in getattr(bundle, "topic_facts", []):
        try:
            svc.enqueue(
                run_id=ctx.run_id,
                project_id=batch.project_id,
                mention_id=getattr(fact, "mention_id", ""),
                fact_type="topic",
                fact_payload=fact.__dict__ if hasattr(fact, "__dict__") else {},
                confidence=float(getattr(fact, "confidence", 0.0)),
            )
        except Exception:
            pass

    return facts


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

_STAGES = [
    (STAGE_NORMALIZATION, _stage_normalize, "enable_normalization"),
    (STAGE_DEDUP, _stage_dedup, "enable_dedup"),
    (STAGE_SPAM, _stage_spam, "enable_spam"),
    (STAGE_THREADS, _stage_threads, "enable_threads"),
    (STAGE_NLP, _stage_nlp, "enable_nlp"),
    (STAGE_ENRICHMENT, _stage_enrichment, "enable_enrichment"),
    (STAGE_REVIEW, _stage_review, "enable_review"),
    (STAGE_REPORTING, _stage_reporting, "enable_reporting"),
    (STAGE_CRISIS, _stage_crisis, "enable_crisis"),
]


def run_pipeline(
    batch: IngestedBatchBundle,
    ctx: RunContext,
    config: PipelineConfig,
) -> PipelineRunResult:
    """Run all enabled pipeline stages in order and return the aggregated result."""
    facts = PipelineFacts()
    stage_results: list[StageResult] = []

    for stage_name, stage_fn, flag_attr in _STAGES:
        if not getattr(config, flag_attr, False):
            stage_results.append(
                StageResult(
                    stage_name=stage_name,
                    elapsed_seconds=0.0,
                    records_in=len(batch.records),
                    records_out=len(batch.records),
                    skipped=True,
                )
            )
            continue

        facts, sr = _run_stage(stage_name, stage_fn, facts, batch, ctx, config)
        stage_results.append(sr)

    timings = _collect_timings([sr for sr in stage_results if not sr.skipped])

    result = PipelineRunResult(
        run_id=ctx.run_id,
        total_valid_records=len(batch.records),
        nlp_facts=facts.nlp_facts,
        nlp_input_records=facts.nlp_input_records,
        filtered_out_unsupported_language=facts.filtered_out_unsupported_language,
        insight_cards=facts.insight_cards,
        bi_bundle=facts.bi_bundle,
        crisis_assessment=facts.crisis_assessment,
        stage_timings=timings,
        stage_results=stage_results,
    )

    # Attach run manifest
    result.run_manifest = build_run_manifest(ctx, result, config)

    return result


__all__ = ["run_pipeline"]

"""build_marts.py — assembles MartBundle from pipeline facts.

Port of core-analysis/src/smap/marts/builder.py.
Key changes vs original:
  - MentionRecord is a dataclass (not pydantic) → use custom serializer
  - ThreadSummary is a dataclass → use dataclasses.asdict()
  - EnrichmentBundle facts are pydantic → use model_dump(mode="json")
  - MentionRecord has no task_id → skip that column in dim_projects
  - posted_at is Optional[datetime] → serialize to ISO string for Polars str ops
  - OntologyRegistryStub replaces full OntologyRegistry
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import polars as pl
from pydantic import BaseModel

from internal.reporting.type import (
    AuthorQualityRecord,
    DedupClusterRecord,
    MartBundle,
    OntologyRegistryStub,
)
from internal.enrichment.type import (
    AspectOpinionFact,
    EntityCandidateClusterFact,
    EntityFact,
    IntentFact,
    IssueSignalFact,
    SentimentFact,
    TargetSentimentFact,
    TopicArtifactFact,
    TopicFact,
)


# ---------------------------------------------------------------------------
# Internal serialization helpers
# ---------------------------------------------------------------------------


def _frame_from_pydantic(
    records: Sequence[BaseModel],
    model_cls: type[BaseModel],
) -> pl.DataFrame:
    """Convert pydantic BaseModel list → Polars DataFrame."""
    payload = [record.model_dump(mode="json") for record in records]
    if payload:
        return pl.DataFrame(payload, infer_schema_length=len(payload))
    return pl.DataFrame({field_name: [] for field_name in model_cls.model_fields})


def _mention_record_to_dict(rec: Any) -> dict:
    """Serialize a MentionRecord dataclass to a JSON-safe dict.

    Converts datetime fields to ISO strings so Polars treats them as Utf8.
    """
    result = {}
    for f in dataclasses.fields(rec):
        val = getattr(rec, f.name)
        if isinstance(val, datetime):
            result[f.name] = val.isoformat()
        else:
            result[f.name] = val
    return result


def _frame_from_mention_records(records: list[Any]) -> pl.DataFrame:
    """Convert list[MentionRecord] (dataclass) → Polars DataFrame."""
    if not records:
        # Build empty DataFrame with all MentionRecord fields
        sample_fields = (
            [f.name for f in dataclasses.fields(records[0].__class__)]
            if records
            else []
        )
        if not sample_fields:
            # Fallback — use common field names
            return pl.DataFrame(
                {
                    "mention_id": [],
                    "source_uap_id": [],
                    "origin_id": [],
                    "platform": [],
                    "project_id": [],
                    "root_id": [],
                    "parent_id": [],
                    "depth": [],
                    "author_id": [],
                    "author_username": [],
                    "raw_text": [],
                    "normalized_text": [],
                    "normalized_text_compact": [],
                    "language": [],
                    "language_confidence": [],
                    "language_supported": [],
                    "language_rejection_reason": [],
                    "mixed_language_uncertain": [],
                    "text_quality_label": [],
                    "text_quality_flags": [],
                    "text_quality_score": [],
                    "hashtags": [],
                    "urls": [],
                    "emojis": [],
                    "semantic_route_hint": [],
                    "dedup_cluster_id": [],
                    "dedup_kind": [],
                    "dedup_representative_mention_id": [],
                    "dedup_cluster_size": [],
                    "dedup_similarity": [],
                    "dedup_weight": [],
                    "mention_spam_score": [],
                    "author_inorganic_score": [],
                    "mention_suspicious": [],
                    "author_suspicious": [],
                    "suspicion_reason_codes": [],
                    "quality_weight": [],
                    "source_url": [],
                    "posted_at": [],
                    "likes": [],
                    "comments_count": [],
                    "shares": [],
                    "views": [],
                    "sort_score": [],
                }
            )
        return pl.DataFrame({name: [] for name in sample_fields})
    payload = [_mention_record_to_dict(rec) for rec in records]
    return pl.DataFrame(payload, infer_schema_length=len(payload))


def _frame_from_thread_summaries(summaries: list[Any]) -> pl.DataFrame:
    """Convert list[ThreadSummary] (dataclass) → Polars DataFrame."""
    _THREAD_FIELDS = [
        "root_id",
        "total_mentions",
        "total_descendants",
        "max_depth_observed",
        "comment_count",
        "reply_count",
        "top_comment_ids",
        "top_comment_scores",
    ]
    if not summaries:
        return pl.DataFrame({name: [] for name in _THREAD_FIELDS})
    payload = [dataclasses.asdict(s) for s in summaries]
    return pl.DataFrame(payload, infer_schema_length=len(payload))


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def build_mart_bundle(
    mentions: list[Any],
    threads: Any,  # ThreadBundle
    enrichment: Any,  # EnrichmentBundle
    ontology: OntologyRegistryStub | None = None,
    *,
    dedup_clusters: list[DedupClusterRecord] | None = None,
    author_quality: list[AuthorQualityRecord] | None = None,
) -> MartBundle:
    """Assemble a MartBundle from pipeline facts.

    This is a port of core-analysis build_marts() adapted for analysis-srv types.
    """
    if ontology is None:
        ontology = OntologyRegistryStub()

    fact_mentions = _frame_from_mention_records(mentions)
    fact_entity_mentions = _frame_from_pydantic(enrichment.entity_facts, EntityFact)
    fact_entity_candidate_clusters = _frame_from_pydantic(
        enrichment.entity_candidate_clusters, EntityCandidateClusterFact
    )
    fact_threads = _frame_from_thread_summaries(threads.summaries if threads else [])
    fact_dedup_clusters = _frame_from_pydantic(dedup_clusters or [], DedupClusterRecord)
    fact_topics = _frame_from_pydantic(enrichment.topic_facts, TopicFact)
    fact_topic_artifacts = _frame_from_pydantic(
        enrichment.topic_artifacts, TopicArtifactFact
    )
    fact_aspects = _frame_from_pydantic(
        enrichment.aspect_opinion_facts, AspectOpinionFact
    )
    fact_sentiment = _frame_from_pydantic(enrichment.sentiment_facts, SentimentFact)
    fact_target_sentiment = _frame_from_pydantic(
        enrichment.target_sentiment_facts, TargetSentimentFact
    )
    fact_intents = _frame_from_pydantic(enrichment.intent_facts, IntentFact)
    fact_issue_signals = _frame_from_pydantic(
        enrichment.issue_signal_facts, IssueSignalFact
    )
    fact_author_quality = _frame_from_pydantic(
        author_quality or [], AuthorQualityRecord
    )

    # Dimension tables from ontology (may be empty stubs)
    dim_entities = pl.DataFrame(
        [
            {
                "canonical_entity_id": entity.id,
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "entity_kind": entity.entity_kind,
                "knowledge_layer": entity.knowledge_layer,
                "active_linking": entity.active_linking,
                "taxonomy_ids": entity.taxonomy_ids,
            }
            for entity in ontology.entities
        ]
    )
    dim_taxonomy = (
        pl.DataFrame([node.model_dump(mode="json") for node in ontology.taxonomy_nodes])
        if ontology.taxonomy_nodes and hasattr(ontology.taxonomy_nodes[0], "model_dump")
        else pl.DataFrame(
            [vars(node) for node in ontology.taxonomy_nodes]
            if ontology.taxonomy_nodes
            else []
        )
    )
    dim_sources = (
        pl.DataFrame(
            [item.model_dump(mode="json") for item in ontology.source_channels]
        )
        if ontology.source_channels
        and hasattr(ontology.source_channels[0], "model_dump")
        else pl.DataFrame(
            [vars(item) for item in ontology.source_channels]
            if ontology.source_channels
            else []
        )
    )

    # dim_projects — adapted: MentionRecord has no task_id, skip it
    if not fact_mentions.is_empty():
        available_proj_cols = [
            c
            for c in ["project_id", "task_id", "platform"]
            if c in fact_mentions.columns
        ]
        sort_proj_cols = [
            c for c in ["project_id", "task_id"] if c in available_proj_cols
        ]
        dim_projects = (
            fact_mentions.select(available_proj_cols)
            .unique()
            .sort(sort_proj_cols if sort_proj_cols else available_proj_cols[:1])
        )
    else:
        dim_projects = pl.DataFrame([])

    # dim_time — requires posted_at as string (ISO from serialization)
    if not fact_mentions.is_empty() and "posted_at" in fact_mentions.columns:
        try:
            dim_time = (
                fact_mentions.with_columns(
                    pl.col("posted_at")
                    .cast(pl.Utf8)
                    .str.slice(0, 10)
                    .str.to_date("%Y-%m-%d", strict=False)
                    .alias("date")
                )
                .with_columns(
                    pl.col("date").dt.year().alias("year"),
                    pl.col("date").dt.month().alias("month"),
                    pl.col("date").dt.week().alias("week"),
                    pl.col("date").dt.weekday().alias("weekday"),
                )
                .select(["date", "year", "month", "week", "weekday"])
                .unique()
                .sort("date")
            )
        except Exception:
            dim_time = pl.DataFrame([])
    else:
        dim_time = pl.DataFrame([])

    return MartBundle(
        tables={
            "fact_mentions": fact_mentions,
            "fact_entity_mentions": fact_entity_mentions,
            "fact_entity_candidate_clusters": fact_entity_candidate_clusters,
            "fact_threads": fact_threads,
            "fact_dedup_clusters": fact_dedup_clusters,
            "fact_topics": fact_topics,
            "fact_topic_artifacts": fact_topic_artifacts,
            "fact_aspects": fact_aspects,
            "fact_sentiment": fact_sentiment,
            "fact_target_sentiment": fact_target_sentiment,
            "fact_intents": fact_intents,
            "fact_issue_signals": fact_issue_signals,
            "fact_author_quality": fact_author_quality,
            "dim_entities": dim_entities,
            "dim_taxonomy": dim_taxonomy,
            "dim_sources": dim_sources,
            "dim_projects": dim_projects,
            "dim_time": dim_time,
        }
    )


__all__ = ["build_mart_bundle"]

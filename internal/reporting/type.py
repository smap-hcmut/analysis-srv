"""Reporting types.

Contains:
- Contract types ported from core-analysis bi/contracts.py
- BI report pydantic models ported from bi/models.py
- InsightCard ported from insights/models.py
- Stub types: MartBundle, OntologyRegistryStub, DedupClusterRecord, AuthorQualityRecord
- I/O dataclasses: ReportingInput, ReportingOutput
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

import polars as pl
from pydantic import BaseModel, Field

from internal.reporting.constant import BI_SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Contract types (ported from bi/contracts.py)
# ---------------------------------------------------------------------------


class ReportFamily(StrEnum):
    SOV = "share_of_voice"
    BUZZ = "buzz"
    EMERGING_TOPICS = "emerging_topics"
    TOP_ISSUES = "top_issues"
    THREAD_CONTROVERSY = "thread_controversy"
    CREATOR_SOURCE_BREAKDOWN = "creator_source_breakdown"
    INSIGHT_CARDS = "insight_cards"


class MeasurementKind(StrEnum):
    GOLD = "gold_like_direct_aggregate"
    PROXY = "proxy"
    HYBRID = "hybrid"


class ReportContract(BaseModel):
    report_name: str
    report_family: ReportFamily
    report_version: str
    grain: str
    time_window_semantics: str
    ranking_semantics: str
    delta_semantics: str
    unresolved_handling: str
    measurement_kind: MeasurementKind
    intended_use: str
    anti_use: str


# ---------------------------------------------------------------------------
# InsightCard (ported from insights/models.py)
# ---------------------------------------------------------------------------


class InsightCard(BaseModel):
    insight_type: str
    title: str
    summary: str
    supporting_metrics: dict[str, object]
    evidence_references: list[str] = Field(default_factory=list)
    confidence: float
    time_window: str
    filters_used: dict[str, object] = Field(default_factory=dict)
    source_reports: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# BI report pydantic models (ported from bi/models.py)
# ---------------------------------------------------------------------------


class ReportWindow(BaseModel):
    analysis_start: str | None = None
    analysis_end: str | None = None
    delta_current_start: str | None = None
    delta_current_end: str | None = None
    delta_previous_start: str | None = None
    delta_previous_end: str | None = None
    delta_kind: str = "none"
    delta_comparison_mode: str = "none"


class UnresolvedSummary(BaseModel):
    count: int = 0
    ratio: float = 0.0
    notes: str
    reason_breakdown: dict[str, int] = Field(default_factory=dict)


class SOVRow(BaseModel):
    canonical_entity_id: str
    entity_name: str | None = None
    entity_type: str | None = None
    mention_count: int
    mention_share: float
    effective_mention_count: float = 0.0
    effective_mention_share: float = 0.0
    entity_hit_count: int
    entity_hit_share: float
    resolved_mention_count: int
    resolved_mention_share: float
    delta_mention_count: int = 0
    delta_mention_share: float = 0.0
    delta_entity_hit_count: int = 0
    delta_entity_hit_share: float = 0.0
    evidence_references: list[str] = Field(default_factory=list)


class SOVReport(BaseModel):
    contract: ReportContract
    window: ReportWindow
    weighting_mode: str = "raw"
    effective_mention_volume: float = 0.0
    filters_used: dict[str, Any] = Field(default_factory=dict)
    entities: list[SOVRow] = Field(default_factory=list)
    unresolved_summary: UnresolvedSummary


class BuzzEntityRow(BaseModel):
    canonical_entity_id: str
    entity_name: str | None = None
    entity_type: str | None = None
    mention_count: int
    mention_share: float
    effective_mention_count: float = 0.0
    effective_mention_share: float = 0.0
    delta_count: int
    growth_ratio_proxy: float
    buzz_score_proxy: float
    evidence_references: list[str] = Field(default_factory=list)


class BuzzTopicRow(BaseModel):
    reporting_topic_key: str
    reporting_topic_label: str
    label_source: str | None = None
    label_health_score: float | None = None
    reporting_status: str = "reportable"
    raw_topic_keys: list[str] = Field(default_factory=list)
    canonical_evidence_phrases: list[str] = Field(default_factory=list)
    salient_terms: list[str] = Field(default_factory=list)
    supporting_phrases: list[str] = Field(default_factory=list)
    mention_count: int
    mention_share: float
    effective_mention_count: float = 0.0
    effective_mention_share: float = 0.0
    delta_count: int
    growth_ratio_proxy: float
    buzz_score_proxy: float
    quality_score: float | None = None
    usefulness_score: float | None = None
    reportability_score: float | None = None
    artifact_purity_score: float | None = None
    weak_topic: bool = False
    noisy_topic: bool = False
    evidence_references: list[str] = Field(default_factory=list)


class BuzzReport(BaseModel):
    contract: ReportContract
    window: ReportWindow
    weighting_mode: str = "raw"
    effective_mention_volume: float = 0.0
    filters_used: dict[str, Any] = Field(default_factory=dict)
    suppressed_weak_noisy_topics: int = 0
    entity_buzz: list[BuzzEntityRow] = Field(default_factory=list)
    topic_buzz: list[BuzzTopicRow] = Field(default_factory=list)


class EmergingTopicRow(BaseModel):
    reporting_topic_key: str
    reporting_topic_label: str
    label_source: str | None = None
    label_health_score: float | None = None
    effective_topic_key: str | None = None
    effective_topic_label: str | None = None
    raw_topic_key: str
    raw_topic_label: str
    topic_size: int
    growth_delta: float | None = None
    stability_score: float | None = None
    quality_score: float | None = None
    usefulness_score: float | None = None
    reportability_score: float | None = None
    artifact_purity_score: float | None = None
    reporting_status: str = "reportable"
    weak_topic: bool = False
    noisy_topic: bool = False
    quality_reason_flags: list[str] = Field(default_factory=list)
    top_terms: list[str] = Field(default_factory=list)
    canonical_evidence_phrases: list[str] = Field(default_factory=list)
    salient_terms: list[str] = Field(default_factory=list)
    supporting_phrases: list[str] = Field(default_factory=list)
    representative_document_ids: list[str] = Field(default_factory=list)
    representative_texts: list[str] = Field(default_factory=list)


class EmergingTopicsReport(BaseModel):
    contract: ReportContract
    window: ReportWindow
    filters_used: dict[str, Any] = Field(default_factory=dict)
    topics: list[EmergingTopicRow] = Field(default_factory=list)


class TopIssueRow(BaseModel):
    issue_category: str
    issue_fact_count: int
    mention_count: int
    mention_prevalence_ratio: float
    issue_pressure_proxy: float
    growth_delta_mentions: int
    severity_mix: dict[str, float] = Field(default_factory=dict)
    evidence_mode_mix: dict[str, float] = Field(default_factory=dict)
    evidence_references: list[str] = Field(default_factory=list)


class TopIssuesReport(BaseModel):
    contract: ReportContract
    window: ReportWindow
    filters_used: dict[str, Any] = Field(default_factory=dict)
    issues: list[TopIssueRow] = Field(default_factory=list)


class ThreadControversyRow(BaseModel):
    root_id: str
    total_mentions: int
    controversy_score_proxy: float
    reply_density_proxy: float
    recursion_proxy: float
    mixed_sentiment_proxy: float
    author_diversity_proxy: float
    issue_diversity_proxy: float
    evidence_references: list[str] = Field(default_factory=list)


class ThreadControversyReport(BaseModel):
    contract: ReportContract
    window: ReportWindow
    filters_used: dict[str, Any] = Field(default_factory=dict)
    threads: list[ThreadControversyRow] = Field(default_factory=list)


class CreatorBreakdownRow(BaseModel):
    creator_id: str
    mention_count: int
    conversation_share: float
    top_topic_keys: list[str] = Field(default_factory=list)
    top_issue_categories: list[str] = Field(default_factory=list)
    controversy_thread_count: int = 0
    evidence_references: list[str] = Field(default_factory=list)


class ThreadInitiatorRow(BaseModel):
    initiator_id: str
    thread_count: int
    share_of_threads: float


class SourceBreakdownRow(BaseModel):
    source_platform: str
    mention_count: int
    conversation_share: float
    top_topic_keys: list[str] = Field(default_factory=list)
    top_issue_categories: list[str] = Field(default_factory=list)


class CreatorSourceBreakdownReport(BaseModel):
    contract: ReportContract
    window: ReportWindow
    filters_used: dict[str, Any] = Field(default_factory=dict)
    creators: list[CreatorBreakdownRow] = Field(default_factory=list)
    thread_initiators: list[ThreadInitiatorRow] = Field(default_factory=list)
    sources: list[SourceBreakdownRow] = Field(default_factory=list)


class InsightCardBundle(BaseModel):
    contract: ReportContract
    window: ReportWindow
    filters_used: dict[str, Any] = Field(default_factory=dict)
    cards: list[InsightCard] = Field(default_factory=list)


class BIReportBundle(BaseModel):
    bi_schema_version: str = BI_SCHEMA_VERSION
    sov_report: SOVReport
    buzz_report: BuzzReport
    emerging_topics_report: EmergingTopicsReport
    top_issues_report: TopIssuesReport
    thread_controversy_report: ThreadControversyReport
    creator_source_breakdown_report: CreatorSourceBreakdownReport
    insight_card_bundle: InsightCardBundle


# ---------------------------------------------------------------------------
# MartBundle — thin dataclass wrapper around polars DataFrames
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class MartBundle:
    tables: dict[str, pl.DataFrame]


# ---------------------------------------------------------------------------
# Stub models for optional upstream data (empty at Phase 5)
# ---------------------------------------------------------------------------


class DedupClusterRecord(BaseModel):
    """Stub for dedup cluster records.  Passed empty at Phase 5."""

    cluster_id: str = ""
    mention_ids: list[str] = Field(default_factory=list)
    cluster_kind: str = "exact"
    representative_mention_id: str = ""


class AuthorQualityRecord(BaseModel):
    """Stub for author quality records.  Passed empty at Phase 5."""

    author_id: str = ""
    quality_score: float = 0.0
    quality_tier: str = "normal"
    inorganic_score: float = 0.0


# ---------------------------------------------------------------------------
# OntologyRegistryStub — minimal stub that satisfies build_marts() usage
# (accesses .entities, .taxonomy_nodes, .source_channels only)
# ---------------------------------------------------------------------------


@dataclass
class OntologyRegistryStub:
    """Minimal ontology stub that satisfies build_marts()'s attribute access."""

    entities: list = field(default_factory=list)
    taxonomy_nodes: list = field(default_factory=list)
    source_channels: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# I/O dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ReportingInput:
    run_id: str
    project_id: str
    campaign_id: str
    mentions: list[Any]  # list[MentionRecord]
    thread_bundle: Any  # ThreadBundle
    enrichment_bundle: Any  # EnrichmentBundle
    ontology: Optional[OntologyRegistryStub] = None
    author_quality: Optional[list[AuthorQualityRecord]] = None


@dataclass
class ReportingOutput:
    mart_bundle: MartBundle
    bi_reports: BIReportBundle
    layer1_payload: dict
    layer2_payloads: list[dict]


__all__ = [
    "ReportFamily",
    "MeasurementKind",
    "ReportContract",
    "InsightCard",
    "ReportWindow",
    "UnresolvedSummary",
    "SOVRow",
    "SOVReport",
    "BuzzEntityRow",
    "BuzzTopicRow",
    "BuzzReport",
    "EmergingTopicRow",
    "EmergingTopicsReport",
    "TopIssueRow",
    "TopIssuesReport",
    "ThreadControversyRow",
    "ThreadControversyReport",
    "CreatorBreakdownRow",
    "ThreadInitiatorRow",
    "SourceBreakdownRow",
    "CreatorSourceBreakdownReport",
    "InsightCardBundle",
    "BIReportBundle",
    "MartBundle",
    "DedupClusterRecord",
    "AuthorQualityRecord",
    "OntologyRegistryStub",
    "ReportingInput",
    "ReportingOutput",
]

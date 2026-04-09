from dataclasses import dataclass, field
from typing import Any, Optional

from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage
from internal.runtime.type import RunContext


@dataclass
class PipelineServices:
    """Holds injected sub-usecase instances for Phase 3–4 pipeline stages.

    All fields are Optional so the pipeline degrades gracefully when a
    particular usecase has not been wired in yet.
    """

    normalization: Optional[Any] = None  # INormalizationUseCase
    dedup: Optional[Any] = None  # IDeduplicationUseCase
    spam: Optional[Any] = None  # ISpamUseCase
    threads: Optional[Any] = None  # IThreadsUseCase
    nlp_enricher: Optional[Any] = None  # NLPBatchEnricher
    enrichment: Optional[Any] = None  # IEnrichmentUseCase (Phase 4)
    review: Optional[Any] = None  # ReviewUseCase (Phase 4+)
    reporting: Optional[Any] = None  # IReportingUseCase (Phase 5)
    crisis: Optional[Any] = None  # ICrisisUseCase (Phase 6)
    ontology_registry: Optional[Any] = None  # FileOntologyRegistry


@dataclass
class IngestedBatchBundle:
    """A batch of UAP records ready for pipeline processing."""

    records: list[UAPRecord]
    project_id: str
    campaign_id: str = ""
    source_run_id: Optional[str] = None


@dataclass
class NLPFact:
    """Per-document NLP enrichment facts produced by the STAGE_NLP stage."""

    uap_id: str
    insight_message: InsightMessage
    uap_record: UAPRecord
    analytics_result: Optional[Any] = None  # AnalyticsResult — for post_insight writes


@dataclass
class PipelineFacts:
    """Accumulates outputs across pipeline stages within a single run."""

    # Stage outputs (populated incrementally)
    normalized_records: list[Any] = field(
        default_factory=list
    )  # Phase 3: MentionRecord
    dedup_clusters: list[Any] = field(default_factory=list)  # Phase 3
    spam_scores: list[Any] = field(default_factory=list)  # Phase 3
    thread_bundles: list[Any] = field(default_factory=list)  # Phase 3
    nlp_facts: list[NLPFact] = field(default_factory=list)  # Phase 4
    enrichment_bundle: Optional[Any] = None  # Phase 4: EnrichmentBundle
    insight_cards: list[Any] = field(default_factory=list)  # Phase 5
    bi_bundle: Optional[Any] = None  # Phase 5
    crisis_assessment: Optional[Any] = None  # Phase 6: CrisisAssessment


@dataclass
class StageResult:
    """Result of a single pipeline stage execution."""

    stage_name: str
    elapsed_seconds: float
    records_in: int
    records_out: int
    skipped: bool = False
    error: Optional[str] = None


@dataclass
class PipelineRunResult:
    """Aggregated result of a complete pipeline run."""

    run_id: str
    total_valid_records: int
    nlp_facts: list[NLPFact] = field(default_factory=list)
    insight_cards: list[Any] = field(default_factory=list)
    bi_bundle: Optional[Any] = None
    crisis_assessment: Optional[Any] = None  # Phase 6: CrisisAssessment
    stage_timings: dict[str, float] = field(default_factory=dict)
    stage_results: list[StageResult] = field(default_factory=list)
    run_manifest: Optional[dict] = None


@dataclass
class PipelineConfig:
    """Feature flags and injected services for pipeline stages.

    Stages are enabled incrementally per phase; services must be provided
    for any stage that is enabled.
    """

    enable_normalization: bool = True  # Phase 3 — but stub runs in Phase 2
    enable_dedup: bool = False  # Phase 3
    enable_spam: bool = False  # Phase 3
    enable_threads: bool = False  # Phase 3
    enable_nlp: bool = False  # NLP enrichment (replaces legacy analytics pipeline)
    enable_enrichment: bool = False  # Phase 4
    enable_review: bool = False  # Phase 4+: low-confidence fact review queue
    enable_reporting: bool = False  # Phase 5
    enable_crisis: bool = False  # Phase 6
    services: PipelineServices = field(default_factory=PipelineServices)


__all__ = [
    "IngestedBatchBundle",
    "NLPFact",
    "PipelineFacts",
    "PipelineServices",
    "StageResult",
    "PipelineRunResult",
    "PipelineConfig",
]

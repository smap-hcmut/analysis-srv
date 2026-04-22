"""test_crisis.py — Phase 6: Crisis hardening integration tests.

Gate criteria:
- assess_crisis() returns crisis_level="none" for empty BI bundle
- assess_crisis() returns crisis_level="watch" for issue_pressure=7.0 (medium, composite=1.0)
- assess_crisis() returns crisis_level="warning" for two high-severity signals
  (issue_pressure=15 + controversy=0.7 → composite=3.6 ≥ 2.5)
- assess_crisis() returns crisis_level="critical" for pressure ≥ 25 (critical_like_proxy)
- CrisisAssessment.is_actionable() returns True for non-"none" levels
- OutboxRecord.new() generates a valid UUID id
- relay_pending_records() with stub conn+producer: sent=1, failed=0 for happy path
- relay_pending_records() with failing producer: failed=1, sent=0
- Full pipeline with enable_crisis=True produces result.crisis_assessment not None
- run_manifest includes crisis_level key
- All 123 previously-passing tests are unaffected
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Helpers — minimal BIReportBundle construction
# ---------------------------------------------------------------------------


def _make_contract(name: str = "test", family: str = "top_issues"):
    from internal.reporting.type import ReportContract, ReportFamily, MeasurementKind

    family_map = {
        "top_issues": ReportFamily.TOP_ISSUES,
        "thread_controversy": ReportFamily.THREAD_CONTROVERSY,
        "sov": ReportFamily.SOV,
        "buzz": ReportFamily.BUZZ,
        "emerging_topics": ReportFamily.EMERGING_TOPICS,
        "creator_source_breakdown": ReportFamily.CREATOR_SOURCE_BREAKDOWN,
        "insight_cards": ReportFamily.INSIGHT_CARDS,
    }
    return ReportContract(
        report_name=name,
        report_family=family_map.get(family, ReportFamily.TOP_ISSUES),
        report_version="0.0.1-test",
        grain="mention",
        time_window_semantics="fixed",
        ranking_semantics="desc",
        delta_semantics="none",
        unresolved_handling="exclude",
        measurement_kind=MeasurementKind.PROXY,
        intended_use="unit-test",
        anti_use="production",
    )


def _empty_window():
    from internal.reporting.type import ReportWindow

    return ReportWindow()


def _make_bi_bundle(
    issue_pressure: float | None = None,
    controversy_score: float | None = None,
    neg_entity_count: int = 0,
    total_entity_count: int = 0,
):
    """Build a minimal BIReportBundle for crisis testing."""
    from internal.reporting.type import (
        BIReportBundle,
        SOVReport,
        SOVRow,
        BuzzReport,
        EmergingTopicsReport,
        TopIssueRow,
        TopIssuesReport,
        ThreadControversyRow,
        ThreadControversyReport,
        CreatorSourceBreakdownReport,
        InsightCardBundle,
        UnresolvedSummary,
    )

    # SOV report — entity rows drive sentiment_collapse proxy
    sov_entities = []
    for i in range(total_entity_count):
        sov_entities.append(
            SOVRow(
                canonical_entity_id=f"ent-{i}",
                mention_count=10,
                mention_share=0.1,
                entity_hit_count=5,
                entity_hit_share=0.1,
                resolved_mention_count=10,
                resolved_mention_share=1.0,
                delta_mention_count=-1 if i < neg_entity_count else 1,
            )
        )
    sov_report = SOVReport(
        contract=_make_contract("sov_report", "sov"),
        window=_empty_window(),
        entities=sov_entities,
        unresolved_summary=UnresolvedSummary(count=0, ratio=0.0, notes=""),
    )

    # Buzz report — empty (no unresolved_summary required)
    buzz_report = BuzzReport(
        contract=_make_contract("buzz_report", "buzz"),
        window=_empty_window(),
    )

    # Emerging topics — empty
    emerging_report = EmergingTopicsReport(
        contract=_make_contract("emerging_topics", "emerging_topics"),
        window=_empty_window(),
    )

    # Top issues
    issues = []
    if issue_pressure is not None:
        issues.append(
            TopIssueRow(
                issue_category="quality",
                issue_fact_count=5,
                mention_count=10,
                mention_prevalence_ratio=0.3,
                issue_pressure_proxy=issue_pressure,
                growth_delta_mentions=2,
            )
        )
    top_issues_report = TopIssuesReport(
        contract=_make_contract("top_issues", "top_issues"),
        window=_empty_window(),
        issues=issues,
    )

    # Thread controversy
    threads = []
    if controversy_score is not None:
        threads.append(
            ThreadControversyRow(
                root_id="thread-001",
                total_mentions=20,
                controversy_score_proxy=controversy_score,
                reply_density_proxy=0.3,
                recursion_proxy=0.2,
                mixed_sentiment_proxy=0.4,
                author_diversity_proxy=0.5,
                issue_diversity_proxy=0.3,
            )
        )
    thread_report = ThreadControversyReport(
        contract=_make_contract("thread_controversy", "thread_controversy"),
        window=_empty_window(),
        threads=threads,
    )

    creator_report = CreatorSourceBreakdownReport(
        contract=_make_contract("creator_source", "creator_source_breakdown"),
        window=_empty_window(),
    )

    insight_bundle = InsightCardBundle(
        contract=_make_contract("insight_cards", "insight_cards"),
        window=_empty_window(),
    )

    return BIReportBundle(
        sov_report=sov_report,
        buzz_report=buzz_report,
        emerging_topics_report=emerging_report,
        top_issues_report=top_issues_report,
        thread_controversy_report=thread_report,
        creator_source_breakdown_report=creator_report,
        insight_card_bundle=insight_bundle,
    )


# ---------------------------------------------------------------------------
# Crisis detection — unit tests
# ---------------------------------------------------------------------------


def test_assess_crisis_empty_bundle_returns_none():
    """Empty BI bundle (no issues, threads, entities) → crisis_level='none'."""
    from internal.crisis.usecase.assess_crisis import assess_crisis

    bi = _make_bi_bundle()
    result = assess_crisis(
        run_id="run-001",
        project_id="proj-001",
        campaign_id="camp-001",
        reports=bi,
    )

    assert result.crisis_level == "none"
    assert result.signals == []
    assert result.composite_crisis_score == 0.0
    assert result.is_actionable() is False


def test_assess_crisis_watch_level_for_medium_pressure():
    """issue_pressure=7.0 (medium severity, weight=1.0) → composite=1.0 → 'watch'."""
    from internal.crisis.usecase.assess_crisis import assess_crisis

    bi = _make_bi_bundle(issue_pressure=7.0)
    result = assess_crisis(
        run_id="run-002",
        project_id="proj-001",
        campaign_id="camp-001",
        reports=bi,
    )

    assert result.crisis_level == "watch"
    assert len(result.signals) == 1
    assert result.signals[0].signal_type == "issue_pressure"
    assert result.signals[0].severity == "medium"
    assert abs(result.composite_crisis_score - 1.0) < 1e-6
    assert result.is_actionable() is True


def test_assess_crisis_warning_level_for_two_high_signals():
    """pressure=15 (high, 1.8) + controversy=0.7 (high, 1.8) → composite=3.6 → 'warning'."""
    from internal.crisis.usecase.assess_crisis import assess_crisis

    bi = _make_bi_bundle(issue_pressure=15.0, controversy_score=0.7)
    result = assess_crisis(
        run_id="run-003",
        project_id="proj-001",
        campaign_id="camp-001",
        reports=bi,
    )

    assert result.crisis_level == "warning"
    assert len(result.signals) == 2
    assert abs(result.composite_crisis_score - 3.6) < 1e-4
    assert result.is_actionable() is True


def test_assess_crisis_critical_level_for_extreme_pressure():
    """pressure=30 (≥25, critical_like_proxy) → crisis_level='critical' regardless of composite."""
    from internal.crisis.usecase.assess_crisis import assess_crisis

    bi = _make_bi_bundle(issue_pressure=30.0)
    result = assess_crisis(
        run_id="run-004",
        project_id="proj-001",
        campaign_id="camp-001",
        reports=bi,
    )

    assert result.crisis_level == "critical"
    assert any(s.severity == "critical_like_proxy" for s in result.signals)
    assert result.is_actionable() is True


def test_crisis_assessment_is_actionable():
    """is_actionable() must be False for 'none' and True for watch/warning/critical."""
    from internal.crisis.type import CrisisAssessment

    def _make(level: str) -> CrisisAssessment:
        return CrisisAssessment(
            run_id="r",
            project_id="p",
            campaign_id="c",
            crisis_level=level,  # type: ignore[arg-type]
        )

    assert _make("none").is_actionable() is False
    assert _make("watch").is_actionable() is True
    assert _make("warning").is_actionable() is True
    assert _make("critical").is_actionable() is True


# ---------------------------------------------------------------------------
# CrisisUseCase — integration
# ---------------------------------------------------------------------------


def test_crisis_usecase_end_to_end():
    """CrisisUseCase.assess() must return a CrisisOutput with a CrisisAssessment."""
    from internal.crisis.usecase.new import new_crisis_usecase
    from internal.crisis.type import CrisisInput, CrisisOutput, CrisisAssessment

    svc = new_crisis_usecase()
    bi = _make_bi_bundle(issue_pressure=15.0, controversy_score=0.7)
    inp = CrisisInput(
        run_id="run-uc-001",
        project_id="proj-001",
        campaign_id="camp-001",
        bi_reports=bi,
    )
    output = svc.assess(inp)

    assert isinstance(output, CrisisOutput)
    assert isinstance(output.assessment, CrisisAssessment)
    assert output.assessment.crisis_level in ("none", "watch", "warning", "critical")


# ---------------------------------------------------------------------------
# Outbox — unit tests
# ---------------------------------------------------------------------------


def test_outbox_record_new_generates_valid_uuid():
    """OutboxRecord.new() must generate a string parseable as a UUID."""
    from internal.outbox.type import OutboxRecord

    record = OutboxRecord.new("run-001", "topic.test", {"key": "value"})

    # Must be parseable as UUID4
    parsed = uuid.UUID(record.id)
    assert str(parsed) == record.id
    assert record.run_id == "run-001"
    assert record.topic == "topic.test"
    assert record.payload == {"key": "value"}
    assert record.status == "pending"


def test_outbox_record_new_generates_unique_ids():
    """Consecutive OutboxRecord.new() calls must produce different IDs."""
    from internal.outbox.type import OutboxRecord

    ids = {OutboxRecord.new("r", "t", {}).id for _ in range(20)}
    assert len(ids) == 20


# ---------------------------------------------------------------------------
# Outbox relay — stub-based tests
# ---------------------------------------------------------------------------


class _StubCursor:
    """Minimal cursor stub — returns rows for SELECT, empty for other SQL."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict]:
        return self._rows


class _StubConn:
    """Minimal synchronous DB connection stub."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []
        self.executed: list[tuple[str, object]] = []

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql: str, params: object = None) -> _StubCursor:
        self.executed.append((sql, params))
        if "SELECT" in sql.upper():
            return _StubCursor(self._rows)
        return _StubCursor([])


class _StubProducer:
    """Minimal Kafka producer stub that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    def send(self, topic: str, value: bytes) -> None:
        self.sent.append((topic, value))


class _FailingProducer:
    """Kafka producer stub that always raises."""

    def send(self, topic: str, value: bytes) -> None:
        raise RuntimeError("Kafka broker unavailable")


def test_relay_pending_records_happy_path():
    """relay_pending_records() must mark the record sent and return sent=1, failed=0."""
    from internal.outbox.usecase.relay_outbox import relay_pending_records

    rows = [
        {
            "id": "rec-001",
            "run_id": "run-001",
            "topic": "test.topic",
            "payload": {"x": 1},
        }
    ]
    conn = _StubConn(rows)
    producer = _StubProducer()

    result = relay_pending_records(conn, producer)

    assert result.attempted == 1
    assert result.sent == 1
    assert result.failed == 0
    assert len(producer.sent) == 1
    assert producer.sent[0][0] == "test.topic"


def test_relay_pending_records_empty_queue():
    """relay_pending_records() with no pending records must return all-zero counts."""
    from internal.outbox.usecase.relay_outbox import relay_pending_records

    conn = _StubConn([])
    producer = _StubProducer()

    result = relay_pending_records(conn, producer)

    assert result.attempted == 0
    assert result.sent == 0
    assert result.failed == 0


def test_relay_pending_records_failing_producer():
    """relay_pending_records() with a failing producer must record failed=1, sent=0."""
    from internal.outbox.usecase.relay_outbox import relay_pending_records

    rows = [
        {
            "id": "rec-002",
            "run_id": "run-002",
            "topic": "test.topic",
            "payload": {"y": 2},
        }
    ]
    conn = _StubConn(rows)
    producer = _FailingProducer()

    result = relay_pending_records(conn, producer)

    assert result.attempted == 1
    assert result.sent == 0
    assert result.failed == 1


# ---------------------------------------------------------------------------
# Full pipeline — crisis stage integration
# ---------------------------------------------------------------------------


def _make_mention(i: int):
    from internal.normalization.type import MentionRecord

    return MentionRecord(
        mention_id=f"m{i:04d}",
        source_uap_id=f"uap{i:04d}",
        origin_id=f"doc{i:04d}",
        platform="facebook",
        project_id="proj-crisis",
        root_id=f"m{i:04d}",
        author_id=f"author{i % 5}",
        raw_text=f"mention text {i}",
        normalized_text=f"mention text {i}",
        posted_at=datetime(2025, 3, 1 + (i % 28), tzinfo=timezone.utc),
    )


def test_pipeline_crisis_stage_produces_assessment():
    """Pipeline with enable_crisis=True must produce a non-None crisis_assessment."""
    from internal.model.uap import UAPRecord, UAPIngest, UAPContent
    from internal.pipeline.type import (
        IngestedBatchBundle,
        PipelineConfig,
        PipelineServices,
    )
    from internal.pipeline.usecase.run_pipeline import run_pipeline
    from internal.runtime.type import RunContext
    from internal.normalization.usecase.new import New as new_normalization_usecase
    from internal.reporting.usecase.new import new_reporting_usecase
    from internal.crisis.usecase.new import new_crisis_usecase

    records = [
        UAPRecord(
            ingest=UAPIngest(project_id="proj-crisis"),
            content=UAPContent(doc_id=f"doc{i}", text=f"sample mention text {i}"),
        )
        for i in range(15)
    ]
    batch = IngestedBatchBundle(
        records=records,
        project_id="proj-crisis",
        campaign_id="camp-crisis",
    )
    ctx = RunContext(run_id="run-crisis-pipeline-001", project_id="proj-crisis")
    config = PipelineConfig(
        enable_normalization=True,
        enable_reporting=True,
        enable_crisis=True,
        services=PipelineServices(
            normalization=new_normalization_usecase(),
            reporting=new_reporting_usecase(),
            crisis=new_crisis_usecase(),
        ),
    )

    result = run_pipeline(batch, ctx, config)

    assert result.crisis_assessment is not None
    assert result.crisis_assessment.crisis_level in (
        "none",
        "watch",
        "warning",
        "critical",
    )
    assert result.crisis_assessment.run_id == "run-crisis-pipeline-001"
    assert result.crisis_assessment.project_id == "proj-crisis"


def test_pipeline_crisis_stage_skipped_when_no_bi_bundle():
    """Pipeline with enable_crisis=True but enable_reporting=False must skip crisis (no bi_bundle)."""
    from internal.model.uap import UAPRecord, UAPIngest, UAPContent
    from internal.pipeline.type import (
        IngestedBatchBundle,
        PipelineConfig,
        PipelineServices,
    )
    from internal.pipeline.usecase.run_pipeline import run_pipeline
    from internal.runtime.type import RunContext
    from internal.normalization.usecase.new import New as new_normalization_usecase
    from internal.crisis.usecase.new import new_crisis_usecase

    records = [
        UAPRecord(
            ingest=UAPIngest(project_id="proj-crisis"),
            content=UAPContent(doc_id=f"doc{i}", text=f"text {i}"),
        )
        for i in range(5)
    ]
    batch = IngestedBatchBundle(records=records, project_id="proj-crisis")
    ctx = RunContext(run_id="run-crisis-skip-001", project_id="proj-crisis")
    config = PipelineConfig(
        enable_normalization=True,
        enable_reporting=False,  # no reporting → no bi_bundle → crisis skips
        enable_crisis=True,
        services=PipelineServices(
            normalization=new_normalization_usecase(),
            crisis=new_crisis_usecase(),
        ),
    )

    result = run_pipeline(batch, ctx, config)

    # Crisis stage runs but skips because bi_bundle is None
    assert result.crisis_assessment is None


def test_run_manifest_includes_crisis_level():
    """run_manifest dict must include a 'crisis_level' key after pipeline run."""
    from internal.model.uap import UAPRecord, UAPIngest, UAPContent
    from internal.pipeline.type import (
        IngestedBatchBundle,
        PipelineConfig,
        PipelineServices,
    )
    from internal.pipeline.usecase.run_pipeline import run_pipeline
    from internal.runtime.type import RunContext
    from internal.normalization.usecase.new import New as new_normalization_usecase
    from internal.reporting.usecase.new import new_reporting_usecase
    from internal.crisis.usecase.new import new_crisis_usecase

    records = [
        UAPRecord(
            ingest=UAPIngest(project_id="proj-manifest"),
            content=UAPContent(doc_id=f"doc{i}", text=f"text {i}"),
        )
        for i in range(5)
    ]
    batch = IngestedBatchBundle(records=records, project_id="proj-manifest")
    ctx = RunContext(run_id="run-manifest-crisis-001", project_id="proj-manifest")
    config = PipelineConfig(
        enable_normalization=True,
        enable_reporting=True,
        enable_crisis=True,
        services=PipelineServices(
            normalization=new_normalization_usecase(),
            reporting=new_reporting_usecase(),
            crisis=new_crisis_usecase(),
        ),
    )

    result = run_pipeline(batch, ctx, config)

    assert result.run_manifest is not None
    assert "crisis_level" in result.run_manifest
    assert result.run_manifest["crisis_level"] in (
        "none",
        "watch",
        "warning",
        "critical",
    )


def test_run_manifest_includes_language_filter_counters():
    """run_manifest must expose NLP input/output and unsupported-language counters."""
    from internal.model.uap import UAPRecord, UAPIngest, UAPContent
    from internal.pipeline.type import IngestedBatchBundle, PipelineConfig, PipelineServices
    from internal.pipeline.usecase.run_pipeline import run_pipeline
    from internal.runtime.type import RunContext
    from internal.normalization.usecase.new import New as new_normalization_usecase

    records = [
        UAPRecord(
            ingest=UAPIngest(project_id="proj-lang-filter"),
            content=UAPContent(doc_id="doc-vi", text="Xin chao ban"),
        ),
        UAPRecord(
            ingest=UAPIngest(project_id="proj-lang-filter"),
            content=UAPContent(doc_id="doc-id", text="ini adalah bahasa indonesia"),
        ),
    ]
    batch = IngestedBatchBundle(records=records, project_id="proj-lang-filter")
    ctx = RunContext(run_id="run-manifest-lang-001", project_id="proj-lang-filter")
    config = PipelineConfig(
        enable_normalization=True,
        enable_nlp=False,
        services=PipelineServices(
            normalization=new_normalization_usecase(),
        ),
    )

    result = run_pipeline(batch, ctx, config)

    assert result.run_manifest is not None
    assert "nlp_input_records" in result.run_manifest
    assert "nlp_output_records" in result.run_manifest
    assert "filtered_out_unsupported_language" in result.run_manifest
    assert result.run_manifest["nlp_input_records"] == 0
    assert result.run_manifest["nlp_output_records"] == 0
    assert result.run_manifest["filtered_out_unsupported_language"] == 1


# ---------------------------------------------------------------------------
# Observability — smoke test
# ---------------------------------------------------------------------------


def test_observability_metrics_importable():
    """observability.metrics must import without error even if prometheus is absent."""
    from internal.observability.metrics import (
        pipeline_runs_total,
        stage_duration_seconds,
        kafka_publish_total,
        crisis_level_gauge,
        PROMETHEUS_AVAILABLE,
    )

    assert isinstance(PROMETHEUS_AVAILABLE, bool)
    # Metrics must be callable (either real or stub)
    # Calling .labels() must not raise
    _ = pipeline_runs_total.labels(status="success")
    _ = stage_duration_seconds.labels(stage="crisis")
    _ = kafka_publish_total.labels(topic="t", status="sent")
    _ = crisis_level_gauge.labels(project_id="proj-001")

"""test_reporting.py — Phase 5: Reporting/Insights integration tests.

Gate criteria:
- build_mart_bundle() completes without error for 50 mentions
- BIReportBundle is non-null with expected structure
- InsightCardBundle.cards list exists (may be empty without entity facts)
- layer1_payload is dict with required keys
- layer2_payloads is a list
- Full pipeline with enable_reporting=True produces bi_bundle + insight_cards
- All 113 previously-passing tests are unaffected
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from internal.enrichment.type import EnrichmentBundle
from internal.normalization.type import MentionRecord
from internal.reporting.type import (
    BIReportBundle,
    OntologyRegistryStub,
    ReportingInput,
)
from internal.reporting.usecase.build_marts import build_mart_bundle
from internal.reporting.usecase.build_bi_reports import build_report_bundle
from internal.reporting.usecase.build_layer1_payload import build_layer1_payload
from internal.reporting.usecase.build_layer2_payload import build_layer2_payloads
from internal.reporting.usecase.new import new_reporting_usecase
from internal.threads.type import ThreadBundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mention(i: int) -> MentionRecord:
    return MentionRecord(
        mention_id=f"m{i:04d}",
        source_uap_id=f"uap{i:04d}",
        origin_id=f"doc{i:04d}",
        platform="facebook",
        project_id="proj-test",
        root_id=f"m{i:04d}",
        author_id=f"author{i % 10}",
        raw_text=f"mention text number {i}",
        normalized_text=f"mention text number {i}",
        posted_at=datetime(2025, 1, 1 + (i % 28), tzinfo=timezone.utc),
    )


def _make_mentions(n: int = 50) -> list[MentionRecord]:
    return [_make_mention(i) for i in range(n)]


RUN_ID = "run-test-001"
PROJECT_ID = "proj-test"
CAMPAIGN_ID = "camp-test"


# ---------------------------------------------------------------------------
# Unit: build_mart_bundle
# ---------------------------------------------------------------------------


def test_build_mart_bundle_empty_mentions():
    """Should complete without error given zero mentions."""
    mart = build_mart_bundle(
        mentions=[],
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    assert mart is not None
    assert "fact_mentions" in mart.tables


def test_build_mart_bundle_50_mentions():
    """Should build all mart tables for 50 mentions without raising."""
    mentions = _make_mentions(50)
    mart = build_mart_bundle(
        mentions=mentions,
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    assert mart is not None
    assert mart.tables["fact_mentions"].height == 50

    # Required tables must be present
    required = [
        "fact_mentions",
        "fact_entity_mentions",
        "fact_topics",
        "fact_threads",
        "fact_issue_signals",
        "dim_projects",
    ]
    for table in required:
        assert table in mart.tables, f"missing table: {table}"


# ---------------------------------------------------------------------------
# Unit: build_report_bundle
# ---------------------------------------------------------------------------


def test_build_report_bundle_structure():
    """BIReportBundle must have all 7 report sub-objects."""
    mart = build_mart_bundle(
        mentions=_make_mentions(50),
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    bundle = build_report_bundle(mart)

    assert isinstance(bundle, BIReportBundle)
    assert bundle.sov_report is not None
    assert bundle.buzz_report is not None
    assert bundle.emerging_topics_report is not None
    assert bundle.top_issues_report is not None
    assert bundle.thread_controversy_report is not None
    assert bundle.creator_source_breakdown_report is not None
    assert bundle.insight_card_bundle is not None


def test_insight_card_bundle_cards_is_list():
    """InsightCardBundle.cards must be a list (may be empty with no entity facts)."""
    mart = build_mart_bundle(
        mentions=_make_mentions(50),
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    bundle = build_report_bundle(mart)
    assert isinstance(bundle.insight_card_bundle.cards, list)


def test_report_bundle_no_mentions():
    """build_report_bundle must not raise even with zero mentions."""
    mart = build_mart_bundle(
        mentions=[],
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    bundle = build_report_bundle(mart)
    assert bundle is not None


# ---------------------------------------------------------------------------
# Unit: build_layer1_payload
# ---------------------------------------------------------------------------


def test_layer1_payload_required_keys():
    """layer1_payload must contain all top-level required keys."""
    mart = build_mart_bundle(
        mentions=_make_mentions(20),
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    bi = build_report_bundle(mart)
    payload = build_layer1_payload(
        run_id=RUN_ID,
        project_id=PROJECT_ID,
        campaign_id=CAMPAIGN_ID,
        reports=bi,
    )

    required_keys = {
        "schema_version",
        "run_id",
        "project_id",
        "campaign_id",
        "analysis_window",
        "mention_volume",
        "effective_mention_volume",
        "top_entities",
        "top_topics",
        "top_issues",
    }
    missing = required_keys - set(payload.keys())
    assert not missing, f"Layer 1 payload missing keys: {missing}"
    assert payload["run_id"] == RUN_ID
    assert payload["project_id"] == PROJECT_ID
    assert isinstance(payload["top_topics"], list)


# ---------------------------------------------------------------------------
# Unit: build_layer2_payloads
# ---------------------------------------------------------------------------


def test_layer2_payloads_is_list():
    """build_layer2_payloads must return a list."""
    mart = build_mart_bundle(
        mentions=_make_mentions(20),
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    bi = build_report_bundle(mart)
    payloads = build_layer2_payloads(
        run_id=RUN_ID,
        project_id=PROJECT_ID,
        campaign_id=CAMPAIGN_ID,
        reports=bi,
    )
    assert isinstance(payloads, list)


def test_layer2_payload_item_structure():
    """Each Layer 2 item must have required keys when cards exist."""
    mart = build_mart_bundle(
        mentions=_make_mentions(20),
        threads=ThreadBundle(),
        enrichment=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    bi = build_report_bundle(mart)
    payloads = build_layer2_payloads(
        run_id=RUN_ID,
        project_id=PROJECT_ID,
        campaign_id=CAMPAIGN_ID,
        reports=bi,
    )

    # Even if no cards are generated, function must return a list
    assert isinstance(payloads, list)
    for item in payloads:
        required = {
            "run_id",
            "project_id",
            "campaign_id",
            "insight_type",
            "title",
            "summary",
        }
        assert required.issubset(set(item.keys())), (
            f"item missing keys: {required - set(item.keys())}"
        )


# ---------------------------------------------------------------------------
# Integration: ReportingUseCase end-to-end
# ---------------------------------------------------------------------------


def test_reporting_usecase_end_to_end():
    """ReportingUseCase.report() must produce non-null ReportingOutput."""
    svc = new_reporting_usecase()
    inp = ReportingInput(
        run_id=RUN_ID,
        project_id=PROJECT_ID,
        campaign_id=CAMPAIGN_ID,
        mentions=_make_mentions(30),
        thread_bundle=ThreadBundle(),
        enrichment_bundle=EnrichmentBundle(),
        ontology=OntologyRegistryStub(),
    )
    output = svc.report(inp)

    assert output is not None
    assert output.mart_bundle is not None
    assert isinstance(output.bi_reports, BIReportBundle)
    assert isinstance(output.layer1_payload, dict)
    assert isinstance(output.layer2_payloads, list)
    assert output.layer1_payload["run_id"] == RUN_ID


# ---------------------------------------------------------------------------
# Integration: full pipeline with enable_reporting=True
# ---------------------------------------------------------------------------


def test_pipeline_reporting_stage():
    """Pipeline with enable_reporting=True must produce bi_bundle and insight_cards."""
    from internal.pipeline.type import (
        IngestedBatchBundle,
        PipelineConfig,
        PipelineServices,
    )
    from internal.pipeline.usecase.run_pipeline import run_pipeline
    from internal.runtime.type import RunContext
    from internal.model.uap import UAPRecord, UAPIngest, UAPContent

    # Build minimal UAPRecords — pipeline needs normalization svc too
    from internal.normalization.usecase.new import New as new_normalization_usecase

    norm_svc = new_normalization_usecase()
    reporting_svc = new_reporting_usecase()

    records = [
        UAPRecord(
            ingest=UAPIngest(project_id=PROJECT_ID),
            content=UAPContent(doc_id=f"doc{i}", text=f"sample text {i}"),
        )
        for i in range(10)
    ]

    batch = IngestedBatchBundle(
        records=records,
        project_id=PROJECT_ID,
        campaign_id=CAMPAIGN_ID,
    )
    ctx = RunContext(run_id="run-pipeline-test", project_id=PROJECT_ID)
    config = PipelineConfig(
        enable_normalization=True,
        enable_reporting=True,
        services=PipelineServices(
            normalization=norm_svc,
            reporting=reporting_svc,
        ),
    )

    result = run_pipeline(batch, ctx, config)
    assert result.bi_bundle is not None
    assert isinstance(result.insight_cards, list)

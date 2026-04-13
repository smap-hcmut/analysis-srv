# Phase 5 — Marts, BI Reports, InsightCard Generator

> **Depends on:** Phase 4 (produces `EnrichmentBundle`)
> **Source:** `core-analysis/src/smap/marts/builder.py`, `bi/reports.py`, `insights/generator.py`
> **New deps:** `polars>=0.20`, `duckdb>=0.10` (optional: DuckDB for mart persistence)

## Mục tiêu

1. Assemble `MartBundle` (Polars DataFrames) từ facts produced by Phase 3 + 4
2. Build `BIReportBundle` (6 reports + InsightCardBundle) từ MartBundle
3. Publish Layer 1 (`smap.analytics.digest`) và Layer 2 (`smap.analytics.insights`) via contract publisher

Sau phase này, analysis-srv publish đủ cả 3 Layer topics cho mỗi batch run.

## Folder structure

```
internal/reporting/
├── interface.py         # IReportingUseCase
├── type.py              # ReportingInput, ReportingOutput
├── constant.py          # MART_TABLE_NAMES, BI_SCHEMA_VERSION
├── errors.py            # MartBuildError, ReportBuildError
└── usecase/
    ├── new.py
    ├── usecase.py
    ├── build_marts.py           # thin wrapper around core-analysis build_marts()
    ├── build_bi_reports.py      # thin wrapper around core-analysis build_bi_reports()
    ├── build_layer1_payload.py  # MartBundle + BIReportBundle → Layer 1 contract payload
    ├── build_layer2_payload.py  # BIReportBundle → Layer 2 InsightMessage[]
    └── helpers.py               # _safe_float(), _top_n_rows(), _window_to_str()
```

## `type.py`

```python
# internal/reporting/type.py
from dataclasses import dataclass
from smap.marts.builder import MartBundle         # ported
from smap.bi.models import BIReportBundle         # ported
from smap.enrichers.models import EnrichmentBundle
from smap.normalization.models import MentionRecord
from smap.threads.models import ThreadBundle
from smap.ontology.models import OntologyRegistry
from smap.quality.models import AuthorQualityRecord

@dataclass
class ReportingInput:
    run_id: str
    project_id: str
    campaign_id: str
    mentions: list[MentionRecord]
    thread_bundle: ThreadBundle
    enrichment_bundle: EnrichmentBundle
    ontology: OntologyRegistry        # minimal registry — may be empty at Phase 5
    author_quality: list[AuthorQualityRecord] | None = None

@dataclass
class ReportingOutput:
    mart_bundle: MartBundle
    bi_reports: BIReportBundle
    layer1_payload: dict             # ready to publish to smap.analytics.digest
    layer2_payloads: list[dict]      # list of InsightMessage dicts for smap.analytics.insights
```

## `build_marts.py`

```python
# internal/reporting/usecase/build_marts.py
# Direct port — core-analysis/src/smap/marts/builder.py is pure functional, no side effects

from smap.marts.builder import build_marts, MartBundle   # ported
from internal.reporting.type import ReportingInput

def build_mart_bundle(inp: ReportingInput) -> MartBundle:
    """
    Assembles Polars DataFrames from all fact types.
    Delegates entirely to core-analysis build_marts().
    
    IMPORTANT: MentionRecord must have all fields populated before calling this:
        - dedup_weight (from Phase 3 dedup)
        - quality_weight (from Phase 3 spam)
        - root_id, parent_id, depth (from Phase 3 ingestion)
        - platform (from ingestion adapter)
    """
    from smap.dedup.models import DedupClusterRecord  # ported

    return build_marts(
        mentions=inp.mentions,
        threads=inp.thread_bundle,
        enrichment=inp.enrichment_bundle,
        ontology=inp.ontology,
        dedup_clusters=[],          # Phase 5: pass empty — full dedup clusters in Phase 6+
        author_quality=inp.author_quality or [],
    )
```

## `build_bi_reports.py`

```python
# internal/reporting/usecase/build_bi_reports.py
# Direct port — core-analysis/src/smap/bi/reports.py

from smap.bi.reports import build_bi_reports   # ported
from smap.marts.builder import MartBundle
from smap.bi.models import BIReportBundle

def build_report_bundle(mart: MartBundle) -> BIReportBundle:
    """
    Builds 6 BI reports + InsightCardBundle from MartBundle.
    
    Reports produced:
      1. SOVReport          → feeds top_entities in Layer 1 digest
      2. BuzzReport         → feeds top_topics + entity buzz in Layer 1 digest
      3. EmergingTopicsReport  → enriches BuzzTopicRow with emerging flag
      4. TopIssuesReport    → feeds top_issues in Layer 1 digest
      5. ThreadControversyReport
      6. CreatorSourceBreakdownReport
    + InsightCardBundle (7 InsightCard types → Layer 2 messages)
    """
    return build_bi_reports(mart)
```

## `build_layer1_payload.py`

```python
# internal/reporting/usecase/build_layer1_payload.py
# Build Layer 1 (smap.analytics.digest) payload from BIReportBundle
# Contract: contract.md §3.1 — AnalyticsDigestMessage

from smap.bi.models import BIReportBundle, BuzzTopicRow, SOVRow, TopIssueRow
from internal.reporting.usecase.helpers import _safe_float

def build_layer1_payload(
    run_id: str,
    project_id: str,
    campaign_id: str,
    reports: BIReportBundle,
) -> dict:
    """
    Maps BIReportBundle → AnalyticsDigestMessage (contract Layer 1).

    Field mappings:
      sov_report.entities[]    → top_entities[]
      buzz_report.topic_buzz[] → top_topics[]
      top_issues_report.issues[] → top_issues[]
      sov_report.window        → analysis_window
    """
    window = reports.sov_report.window

    top_entities = [
        {
            "entity_id": row.canonical_entity_id,
            "entity_name": row.entity_name,
            "entity_type": row.entity_type,
            "mention_count": row.mention_count,
            "mention_share": row.mention_share,
            "effective_mention_count": row.effective_mention_count,
            "delta_mention_count": row.delta_mention_count,
            "delta_mention_share": row.delta_mention_share,
        }
        for row in reports.sov_report.entities[:10]
    ]

    top_topics = [
        {
            "topic_key": row.reporting_topic_key,
            "topic_label": row.reporting_topic_label,
            "mention_count": row.mention_count,
            "mention_share": row.mention_share,
            # optional v1.2 fields:
            "effective_mention_count": row.effective_mention_count,
            "growth_ratio_proxy": row.growth_ratio_proxy,
            "salient_terms": row.salient_terms[:5],
        }
        for row in reports.buzz_report.topic_buzz[:10]
    ]

    top_issues = [
        {
            "issue_category": row.issue_category,
            "mention_count": row.mention_count,
            "mention_prevalence_ratio": row.mention_prevalence_ratio,
            "issue_pressure_proxy": row.issue_pressure_proxy,
            "severity_mix": row.severity_mix,
            "growth_delta_mentions": row.growth_delta_mentions,
        }
        for row in reports.top_issues_report.issues[:10]
    ]

    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "project_id": project_id,
        "campaign_id": campaign_id,
        "analysis_window": {
            "start": window.analysis_start,
            "end": window.analysis_end,
            "delta_kind": window.delta_kind,
        },
        "top_entities": top_entities,
        "top_topics": top_topics,
        "top_issues": top_issues,
        "mention_volume": sum(r.mention_count for r in reports.sov_report.entities) or None,
        "effective_mention_volume": _safe_float(reports.sov_report.effective_mention_volume),
    }
```

## `build_layer2_payload.py`

```python
# internal/reporting/usecase/build_layer2_payload.py
# Build Layer 2 (smap.analytics.insights) payloads from InsightCardBundle
# Contract: contract.md §3.2 — InsightMessage (one message per InsightCard)

from smap.bi.models import BIReportBundle
from smap.insights.models import InsightCard

def build_layer2_payloads(
    run_id: str,
    project_id: str,
    campaign_id: str,
    reports: BIReportBundle,
) -> list[dict]:
    """
    Maps each InsightCard → one InsightMessage dict.

    Contract insight_type values (7 types):
      share_of_voice_shift, trending_topic, conversation_hotspot,
      emerging_topic, issue_warning, controversy_alert, creator_concentration

    Optional v1.2 fields per card:
      reportability_score, usefulness_score (from supporting_metrics if present)
    """
    cards: list[InsightCard] = reports.insight_card_bundle.cards
    payloads = []
    for card in cards:
        payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "project_id": project_id,
            "campaign_id": campaign_id,
            "insight_type": card.insight_type,
            "title": card.title,
            "summary": card.summary,
            "confidence": card.confidence,
            "time_window": card.time_window,
            "supporting_metrics": card.supporting_metrics,
            "evidence_references": card.evidence_references,
            "source_reports": card.source_reports,
            "filters_used": card.filters_used,
        }
        # Optional v1.2 fields — include if present in supporting_metrics
        if "reportability_score" in card.supporting_metrics:
            payload["reportability_score"] = card.supporting_metrics["reportability_score"]
        if "usefulness_score" in card.supporting_metrics:
            payload["usefulness_score"] = card.supporting_metrics["usefulness_score"]

        payloads.append(payload)
    return payloads
```

## `helpers.py`

```python
# internal/reporting/usecase/helpers.py

def _safe_float(value) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    return None

def _top_n_rows(rows: list, n: int = 10) -> list:
    return rows[:n]

def _window_to_str(window) -> str:
    if window.analysis_start and window.analysis_end:
        return f"{window.analysis_start} to {window.analysis_end}"
    return "all_time"
```

## Wiring trong `run_pipeline.py` (Phase 2 extension)

```python
# internal/pipeline/usecase/run_pipeline.py (update)
from internal.reporting.usecase.build_marts import build_mart_bundle
from internal.reporting.usecase.build_bi_reports import build_report_bundle
from internal.reporting.usecase.build_layer1_payload import build_layer1_payload
from internal.reporting.usecase.build_layer2_payload import build_layer2_payloads
from internal.reporting.type import ReportingInput

# Sau Phase 4 enrichment:
if config.reporting_enabled:
    reporting_inp = ReportingInput(
        run_id=run_id,
        project_id=project_id,
        campaign_id=campaign_id,
        mentions=mentions,
        thread_bundle=thread_bundle,
        enrichment_bundle=enrichment_bundle,
        ontology=_empty_ontology(),   # Phase 5: minimal ontology
        author_quality=author_quality_records,
    )
    mart_bundle = build_mart_bundle(reporting_inp)
    bi_reports = build_report_bundle(mart_bundle)

    layer1 = build_layer1_payload(run_id, project_id, campaign_id, bi_reports)
    layer2_list = build_layer2_payloads(run_id, project_id, campaign_id, bi_reports)

    # Publish via contract_publisher (Phase 1)
    publisher.publish_digest(layer1)
    for insight_msg in layer2_list:
        publisher.publish_insight(insight_msg)
```

## Layer 3 flow (reminder)

Layer 3 (`smap.analytics.nlp`) is published **per-mention** directly from contract publisher
(see Phase 1), not from reporting. It is fed by:
- `sentiment_facts[]` from `EnrichmentBundle`
- `aspect_opinion_facts[]` → `nlp.aspects[]`
- `issue_signal_facts[]` → `nlp.issues[]` (optional v1.2)
- `stance_facts[]` → `nlp.stance` (optional v1.2)
- `intent_facts[]` → `nlp.intent` (optional v1.2)
- `source_influence_facts[]` → `business.influence_tier` (optional v1.2)

## Ontology stub for Phase 5

```python
# internal/reporting/usecase/helpers.py (add)
from smap.ontology.models import OntologyRegistry

def _empty_ontology() -> OntologyRegistry:
    """Stub ontology — no entities, no taxonomy, no source channels.
    Reports will have dim_entities / dim_taxonomy empty DataFrames.
    SOVReport will show 0 entities (all unresolved).
    Acceptable for Phase 5 smoke test.
    """
    return OntologyRegistry(entities=[], taxonomy_nodes=[], source_channels=[])
```

## MartBundle table reference

| Table name | Source |
|---|---|
| `fact_mentions` | `MentionRecord[]` |
| `fact_entity_mentions` | `EntityFact[]` |
| `fact_entity_candidate_clusters` | `EntityCandidateClusterFact[]` |
| `fact_threads` | `ThreadSummary[]` from `ThreadBundle` |
| `fact_dedup_clusters` | `DedupClusterRecord[]` (empty at Phase 5) |
| `fact_topics` | `TopicFact[]` |
| `fact_topic_artifacts` | `TopicArtifactFact[]` |
| `fact_aspects` | `AspectOpinionFact[]` |
| `fact_sentiment` | `SentimentFact[]` |
| `fact_target_sentiment` | `TargetSentimentFact[]` |
| `fact_intents` | `IntentFact[]` |
| `fact_issue_signals` | `IssueSignalFact[]` |
| `fact_author_quality` | `AuthorQualityRecord[]` |
| `dim_entities` | From `OntologyRegistry.entities` |
| `dim_taxonomy` | From `OntologyRegistry.taxonomy_nodes` |
| `dim_sources` | From `OntologyRegistry.source_channels` |
| `dim_projects` | Derived from `fact_mentions` |
| `dim_time` | Derived from `fact_mentions.posted_at` |

## Gate Phase 5

- [ ] `build_mart_bundle()` completes without error for a batch of 50 mentions
- [ ] `BIReportBundle` is non-null (even if most reports have empty rows)
- [ ] `InsightCardBundle.cards` non-empty when mentions have topic and issue facts
- [ ] Layer 1 payload passes JSON schema validation against `contract.md §3.1`
- [ ] Layer 2 payload list passes JSON schema validation against `contract.md §3.2`
- [ ] `smap.analytics.digest` message consumed by a test consumer with correct schema
- [ ] `smap.analytics.insights` messages consumed (at least 1) with correct schema
- [ ] Layer 3 `smap.analytics.nlp` messages (from Phase 1 publisher) pass contract schema

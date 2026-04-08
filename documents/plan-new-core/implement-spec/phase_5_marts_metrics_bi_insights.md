# Phase 5 - Marts, Metrics, BI, Insights

## Objective

Port reporting stack de tao outputs phuc vu business va downstream contracts.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/reporting/usecase/build_marts.py` | `build_marts(mentions, threads, enrichment, ontology, dedup_clusters, author_quality)` | `smap/marts/builder.py::build_marts` (L23) | Build fact/dim marts |
| `internal/pipeline/usecase/run_pipeline.py` | `_build_marts_bundle(...)` | `smap/pipeline.py::_build_marts_bundle` (L100) | Stage adapter |
| `internal/reporting/usecase/build_metrics.py` | `build_metrics(bundle, weighting_mode='raw')` | `smap/analytics/metrics.py::build_metrics` (L160) | Diagnostics/perception/concentration |
| `internal/reporting/usecase/build_bi_reports.py` | `build_bi_reports(bundle, metrics=None, weighting_mode=None)` | `smap/bi/reports.py::build_bi_reports` (L18) | Build BI report bundle |
| `internal/reporting/usecase/build_insights.py` | `build_insight_card_bundle(...)` | `smap/bi/reports.py::_build_insight_card_bundle` (L235) | Insight cards from reports |
| `internal/reporting/usecase/build_insights.py` | `generate_insights(source)` | `smap/insights/generator.py::generate_insights` (L10) | Final insight list |

## Deliverables

- Marts tables.
- metrics.json equivalent.
- BI reports + insight cards.

## Exit criteria

- Report schema tests pass.
- Insight evidence references hop le.

# Phase 6 - Contract Publish, Manifest, Crisis

## Objective

Implement outbound contracts cho knowledge/project va run manifest metadata.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/contract_publisher/usecase/publish_knowledge_batch.py` | `build_batch_completed_payload(run_ctx, docs)` | `NEW` + map theo `document/contract.md` | Build Layer 3 payload |
| `internal/contract_publisher/usecase/publish_knowledge_insights.py` | `build_insights_published_payloads(run_ctx, cards)` | `NEW` + map theo `document/contract.md` | Build Layer 2 payloads |
| `internal/contract_publisher/usecase/publish_knowledge_digest.py` | `build_report_digest_payload(run_ctx, bi_bundle)` | `NEW` + map theo `document/contract.md` | Build Layer 1 payload |
| `internal/contract_publisher/usecase/publish_order.py` | `publish_in_required_order(outbox, run_id)` | `NEW` | Enforce batch -> insights -> digest |
| `internal/runtime/usecase/run_manifest.py` | `summarize_runtime_mode(settings, enrichment, provider_runtime, doctor_report)` | `smap/run_manifest.py::summarize_runtime_mode` (L150) | Runtime mode summary |
| `internal/runtime/usecase/run_manifest.py` | `build_run_manifest(run_id, input_path, settings, enrichment, bi_reports, storage_paths, ...)` | `smap/run_manifest.py::build_run_manifest` (L348) | Manifest model |
| `internal/crisis/usecase/evaluate_rules.py` | `evaluate_crisis_rules(config, window_metrics)` | `NEW` | Rule engine for warning/critical |
| `internal/contract_publisher/usecase/publish_project_crisis.py` | `build_project_crisis_payload(alert)` | `document/analysis-service/05_contract_analysis_to_project_crisis.md` | Build crisis event |
| `internal/contract_publisher/usecase/publish_project_crisis.py` | `publish_project_crisis(alert)` | `NEW` | Publish `project.crisis.detected` |

## Deliverables

- Knowledge payload builders + publish ordering.
- Run manifest generation.
- Crisis event publishing.

## Exit criteria

- Contract validation tests pass.
- Crisis scenarios generate expected severity and payload.

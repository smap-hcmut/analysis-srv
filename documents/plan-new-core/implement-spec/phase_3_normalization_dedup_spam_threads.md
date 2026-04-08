# Phase 3 - Normalization, Dedup, Spam, Threads

## Objective

Port quality pre-processing layer day du truoc enrichment.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/normalization/usecase/normalize_mentions.py` | `normalize_batch(parsed_records, language_id_provider)` | `smap/normalization/service.py::normalize_batch` (L83) | Mention shaping + language routing |
| `internal/pipeline/usecase/run_pipeline.py` | `_normalize_bundle(parsed_records, provider_runtime)` | `smap/pipeline.py::_normalize_bundle` (L86) | Adapter normalize in orchestrator |
| `internal/dedup/usecase/annotate.py` | `DeduplicationService.annotate(mentions)` | `smap/dedup/service.py::DeduplicationService.annotate` (L38) | exact + near dedup |
| `internal/pipeline/usecase/run_pipeline.py` | `_apply_dedup(settings, normalized)` | `smap/pipeline.py::_apply_dedup` (L90) | Apply dedup stage |
| `internal/spam/usecase/annotate.py` | `SpamScoringService.annotate(mentions)` | `smap/quality/spam.py::SpamScoringService.annotate` (L28) | mention + author suspicious scoring |
| `internal/pipeline/usecase/run_pipeline.py` | `_apply_spam(settings, normalized)` | `smap/pipeline.py::_apply_spam` (L95) | Apply spam stage |
| `internal/threads/usecase/build_threads.py` | `build_threads(mentions)` | `smap/threads/service.py::build_threads` (L20) | Thread graph + context |
| `internal/threads/usecase/build_threads.py` | `conversation_slice(mention_id, contexts, window=3)` | `smap/threads/service.py::conversation_slice` (L58) | Context slicing helper |

## Deliverables

- Normalized mentions co quality fields.
- Dedup/spam/thread artifacts san sang cho enrichment.

## Exit criteria

- Dedup/spam benchmark pass.
- Thread lineage tests pass.

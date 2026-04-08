# Phase 1 - Pipeline Runtime and Provider

## Objective

Dung pipeline skeleton va provider runtime de co flow chay thong suot.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/pipeline/interface.py` | `class IPipelineUseCase.process_run(...)` | `smap/pipeline.py::run_pipeline` (L104) | Interface public cho orchestrator |
| `internal/pipeline/usecase/run_pipeline.py` | `run_pipeline(input_path, settings, run_id, progress_cb)` | `smap/pipeline.py::run_pipeline` (L104) | Main orchestrator |
| `internal/pipeline/usecase/run_pipeline.py` | `_build_enricher_service(...)` | `smap/pipeline.py::_build_enricher_service` (L59) | Build enrichment runtime |
| `internal/pipeline/usecase/run_pipeline.py` | `_close_runtime_resources(runtime)` | `smap/pipeline.py::_close_runtime_resources` (L73) | Dong provider resources |
| `internal/runtime/usecase/resolve_ontology.py` | `load_runtime_ontology(settings, records=None)` | `smap/ontology/runtime.py::load_runtime_ontology` (L37) | Chon domain ontology |
| `internal/runtime/usecase/resolve_ontology.py` | `_score_domain(path, records)` | `smap/ontology/runtime.py::_score_domain` (L80) | Corpus auto select |
| `internal/runtime/usecase/resolve_ontology.py` | `_best_domain_score(scored)` | `smap/ontology/runtime.py::_best_domain_score` (L105) | Chon domain cao nhat |
| `internal/providers/usecase/factory.py` | `_build_embedding_provider(settings, ontology)` | `smap/providers/factory.py::_build_embedding_provider` (L79) | ML/fallback embeddings |
| `internal/providers/usecase/factory.py` | `build_language_id_provider(settings)` | `smap/providers/factory.py::build_language_id_provider` (L93) | fasttext/heuristic |
| `internal/providers/usecase/factory.py` | `build_topic_provider(settings, ontology, embedding_provider)` | `smap/providers/factory.py::build_topic_provider` (L111) | ontology topic/fallback |
| `internal/providers/usecase/factory.py` | `build_ner_providers_with_embedding(...)` | `smap/providers/factory.py::build_ner_providers_with_embedding` (L129) | NER providers |
| `internal/providers/usecase/factory.py` | `build_provider_runtime(settings, ontology)` | `smap/providers/factory.py::build_provider_runtime` (L137) | Runtime container |
| `internal/runtime/usecase/doctor.py` | `run_runtime_doctor(settings)` | `smap/runtime/doctor.py::run_runtime_doctor` (L42) | Readiness checks |

## Deliverables

- Pipeline skeleton chay duoc voi provider runtime.
- Doctor report endpoint/command.

## Exit criteria

- Smoke run pass voi sample input.
- Resource close test pass.

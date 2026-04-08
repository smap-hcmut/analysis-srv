# Phase 4 - Enrichment: Entity, Semantic, Topic

## Objective

Port enrichment core va ontology alignment logic.

## Function-level mapping

| Target file (analysis-srv) | Function can implement | Match tu smap-analyse | Notes |
|---|---|---|---|
| `internal/enrichment/usecase/enrich_entities.py` | `prepare(mentions, contexts)` | `smap/enrichers/entity.py::EntityExtractionEnricher.prepare` (L39) | Precompute aliases/prototypes |
| `internal/enrichment/usecase/enrich_entities.py` | `enrich(mention, context)` | `smap/enrichers/entity.py::EntityExtractionEnricher.enrich` (L87) | Entity facts per mention |
| `internal/enrichment/usecase/enrich_entities.py` | `annotate_batch_local_candidates(entity_facts, mentions)` | `smap/enrichers/entity.py::EntityExtractionEnricher.annotate_batch_local_candidates` (L120) | Candidate clusters |
| `internal/enrichment/usecase/enrich_semantic.py` | `enrich(mentions, contexts, entity_facts)` | `smap/enrichers/semantic.py::SemanticInferenceEnricher.enrich` (L74) | sentiment/target/aspect/issue |
| `internal/enrichment/usecase/enrich_topics.py` | `prepare(mentions, contexts, entity_facts, aspect_facts, issue_facts)` | `smap/enrichers/topic.py::TopicCandidateEnricher.prepare` (L65) | Topic prep |
| `internal/enrichment/usecase/enrich_topics.py` | `enrich(mention, context)` | `smap/enrichers/topic.py::TopicCandidateEnricher.enrich` (L464) | Topic facts |
| `internal/enrichment/usecase/enrich_topics.py` | `artifacts()` | `smap/enrichers/topic.py::TopicCandidateEnricher.artifacts` (L468) | Topic artifacts |
| `internal/enrichment/usecase/service.py` | `enrich_mentions(mentions, contexts)` | `smap/enrichers/service.py::EnricherService.enrich_mentions` (L24) | Unified enricher service |
| `internal/enrichment/usecase/topic_quality.py` | `persist_topic_artifact_snapshot(output_dir, artifacts)` | `smap/enrichers/topic_quality.py::persist_topic_artifact_snapshot` (L489) | Snapshot artifact history |
| `internal/pipeline/usecase/run_pipeline.py` | `run_entity_semantic_topic_stages(...)` | `smap/pipeline.py` (entity/semantic/topic blocks) | Split stage blocks thanh functions rieng |

## Deliverables

- Gold facts day du: entity, sentiment, aspects, issues, topics.
- Topic artifacts va snapshot.

## Exit criteria

- Ontology alignment pass.
- Enrichment quality checks pass tren sample dataset.

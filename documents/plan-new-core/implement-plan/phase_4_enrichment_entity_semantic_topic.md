# Phase 4 - Enrichment (Entity, Semantic, Topic)

## Muc tieu

Port enrichment core tu smap-analyse voi ontology-aware behavior.

## Cong viec chinh

1. Port runtime ontology selection (explicit/corpus_auto/fallback).
2. Port entity extraction + canonicalization.
3. Port semantic inference:
   - mention sentiment
   - target sentiment
   - aspect opinions
   - issue signals
4. Port topic candidate generation + topic artifacts.
5. Add alignment checks voi ontology labels.

## Deliverables

- Enrichment facts day du tren gold tables.
- Topic artifacts snapshot.

## Test/validation

- Ontology alignment tests.
- Entity precision/recall smoke benchmark.
- Semantic label consistency tests.

## Exit criteria

- Khong co alignment error tren dataset validation.
- Confidence distribution nam trong range ky vong.

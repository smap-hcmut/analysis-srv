# Phase 1 - Foundation and Skeleton

## Muc tieu

Dung khung clean architecture theo module convention cho cac domain moi.

## Cong viec chinh

1. Tao module skeleton:
   - pipeline
   - ingestion
   - normalization
   - dedup
   - spam
   - enrichment
   - reporting
   - contract_publisher
   - crisis
   - runtime
2. Tao interface va type stubs cho usecases/repositories.
3. Wiring bootstrap trong consumer server.
4. Tao feature flags de rollout tung module.

## Deliverables

- Skeleton code compile/run duoc.
- Dependency wiring map.
- Feature flag matrix.

## Test/validation

- Import/dependency smoke test.
- Minimal e2e fake flow qua skeleton pipeline.

## Exit criteria

- Khong co circular import.
- Core wiring pass smoke test.

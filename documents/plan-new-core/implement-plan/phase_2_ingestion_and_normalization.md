# Phase 2 - Ingestion and Normalization

## Muc tieu

Port ingestion + normalization core tu smap-analyse vao module moi.

## Cong viec chinh

1. Port input adapters cho jsonl/zip/kafka payload.
2. Port UAP parsing va validation.
3. Port normalization:
   - text normalization
   - language detection routing
   - mention model shaping
4. Persist raw + normalized data vao Timescale/Postgre.
5. Implement idempotency key (`event_id`, `uap_id`).

## Deliverables

- Ingestion pipeline hoat dong voi sample batch lon.
- Normalized mention records persist thanh cong.

## Test/validation

- Unit tests parser/validator.
- Integration test ingest -> persist.
- Replay test idempotency.

## Exit criteria

- Ty le parse fail trong nguong cho phep.
- Duplicate handling dung theo spec.

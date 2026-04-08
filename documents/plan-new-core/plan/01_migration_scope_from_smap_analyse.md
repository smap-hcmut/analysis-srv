# Migration Scope from smap-analyse

## Mục tiêu

Tái sử dụng core xử lý từ smap-analyse để nâng cấp analysis-srv thành pipeline phân tích đầy đủ, nhưng vẫn giữ chuẩn clean architecture và tính vận hành production.

## In Scope

- Ingestion UAP hợp nhất và chuẩn hóa schema.
- Runtime ontology/domain selection.
- Core pipeline stages:
  - normalize
  - dedup
  - spam scoring
  - entity extraction
  - semantic inference
  - topic enrichment
  - review queue seeding
  - marts/metrics/bi/insights
- Run manifest và stage timing.
- Crisis detection + event output cho project.
- Contract output cho knowledge.

## Out of Scope (phase đầu)

- UI cho review/human-in-loop.
- Retraining/fine-tuning model.
- Multi-tenant hard isolation bằng hạ tầng riêng.
- Full online feature store.

## Boundary rõ ràng

- Input boundary:
  - Kafka topic inbound từ ingest.
  - Optional batch input từ MinIO path.
- Output boundary:
  - Kafka topics cho knowledge (batch/insights/digest).
  - Kafka topic crisis cho project.
- Persistence boundary:
  - PostgreSQL/Timescale cho operational + analytics store.
  - DuckDB/parquet chỉ dùng như artifact/report nếu cần.

## Yêu cầu không được mất

- Traceability theo trace_id end-to-end.
- Idempotency theo event_id/uap_id.
- Deterministic publish order cho knowledge.
- Domain-specific ontology behavior.

## Success Criteria

- Feature parity với các capability lõi từ smap-analyse.
- Không phá contract hiện có với downstream services.
- Có khả năng rollout theo từng phase, không big-bang.

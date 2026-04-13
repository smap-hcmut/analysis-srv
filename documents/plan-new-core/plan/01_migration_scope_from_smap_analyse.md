# Core Integration Scope

> **Updated:** 2026-04-09

## Mục tiêu

Port `core-analysis` pipeline vào `analysis-srv` theo Python clean architecture convention. `core-analysis` đã **hoàn thiện** (17 stages, full ML stack). Công việc là **port** từng module vào `internal/` và **wire** Kafka I/O.

## Điều KHÔNG thay đổi

| Item | Lý do |
|---|---|
| **Input boundary** | Kafka UAP records từ `ingest-srv` — giữ nguyên format |
| **Python clean architecture convention** | `convention_python.md` — convention hiện tại tiếp tục áp dụng |
| **`pkg/` infrastructure** | `pkg/kafka`, `pkg/postgres`, `pkg/redis`, `pkg/minio` — tái dùng 100% |
| **Các module NLP hiện có** | `internal/sentiment_analysis/`, `internal/intent_classification/`, v.v. — tích hợp vào pipeline mới |
| **Output Kafka interface** | Vẫn dùng shared-libs Kafka producer — chỉ thay đổi topic và payload |

## In Scope — Phải làm

### Bắt buộc (contract với knowledge-srv)

- `internal/contract_publisher/` — publish đúng 3 Kafka topics theo `contract.md v1.2`
- `internal/pipeline/` — orchestrator batch run, quản lý `run_id`, thứ tự publish
- `internal/runtime/` — `run_id` generation, ontology selection, enum normalization

### Port từ core-analysis

- `internal/ingestion/` ← `core-analysis/src/smap/ingestion/` + `contracts/uap.py`
- `internal/normalization/` ← `core-analysis/src/smap/normalization/`
- `internal/dedup/` ← `core-analysis/src/smap/dedup/` (MinHash LSH)
- `internal/spam/` ← `core-analysis/src/smap/quality/` (author inorganic scoring)
- `internal/enrichment/` ← `core-analysis/src/smap/enrichers/` (entity NER, ABSA, topic)
- `internal/reporting/` ← `core-analysis/src/smap/marts/`, `bi/`, `insights/`, `analytics/`
- `internal/storage/` ← `core-analysis/src/smap/storage/` (parquet write, manifest)

### Implement mới (không có trong core-analysis)

- `internal/crisis/` — crisis evaluator theo project config, publish `project.crisis.detected`
- `internal/review/` — review queue (low-confidence items), PostgreSQL persistence

## Out of Scope (phase đầu)

- UI cho human-in-the-loop review
- Model retraining / fine-tuning
- Multi-tenant hard infra isolation
- Full online feature store
- Kafka Streams / stateful processing

## Input Adapter

`core-analysis` nhận input qua CLI (ZIP/JSONL). Khi port vào analysis-srv, `internal/ingestion/` có thêm adapter:

```
Kafka UAPRecord  →  KafkaToIngestedBatchAdapter  →  IngestedBatchBundle  →  pipeline
(giữ nguyên)              (mới trong ingestion)          (core type)
```

Adapter này thuần túy là format conversion. Không đổi gì ở phía Kafka consumer hiện tại.

## Libraries tận dụng từ core-analysis

| Library | Dùng cho | Thay thế cái gì |
|---|---|---|
| **Polars** | Data processing trong pipeline stages | Per-record Python loops |
| **fastText** `lid.176` | Language detection | Không có trong analysis-srv cũ |
| **FAISS** | Entity embedding similarity | Không có |
| **datasketch** MinHash | Near-dedup | Không có |
| **DuckDB** | In-process SQL cho marts/reports | Không có (chỉ cho artifacts) |
| PhoBERT full model | NER, ABSA, topic | PhoBERT ONNX (giữ ONNX cho sentiment — faster) |

## Yêu cầu không được mất

- Traceability theo `trace_id` end-to-end (inbound UAP → core → outbound Kafka)
- Idempotency theo `event_id`/`uap_id`
- Publish ordering: `analytics.batch.completed` → `analytics.insights.published` (×N) → `analytics.report.digest`
- Domain-specific ontology behavior (YAML config per domain)
- `run_id` format: `run-YYYYMMDDTHHMMSSz` (UTC, consistent với core-analysis)

## Success Criteria

- 3 contract topics published với đúng schema per `contract.md v1.2`
- knowledge-srv nhận và index được batch/insights/digest từ staging test
- Feature parity với core-analysis trên sample dataset facial-cleanser
- Không có regression với downstream contracts hiện có
- Phased rollout: không big-bang cutover

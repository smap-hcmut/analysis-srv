# Analysis Service — Core Integration Plan Index

> **Updated:** 2026-04-09
> **Status:** Active

## Bức tranh tổng thể

`core-analysis` (repo của DS team) đã **hoàn thiện** pipeline 17 stage với đầy đủ ML stack (PhoBERT NER/ABSA/sentiment, fastText, FAISS, MinHash LSH, DuckDB, Polars). Mục tiêu của plan này là **port core vào analysis-srv** theo Python clean architecture convention, nối với Kafka I/O hiện có, và wire đủ 3 contract topics cho `knowledge-srv`.

## Trạng thái hiện tại

| Layer | Trạng thái |
|---|---|
| Kafka consumer (nhận UAP records) | ✅ Done — `internal/analytics/delivery/kafka/consumer/` |
| Per-document NLP (sentiment, aspect, intent, keyword, impact) | ✅ Done — `internal/sentiment_analysis/`, `internal/intent_classification/`, v.v. |
| Contract publisher (3 Kafka topics) | ❌ **Chưa có** — critical gap |
| Pipeline orchestrator (batch run_id, stage sequencing) | ❌ Chưa có |
| Enrichment nâng cao (entity NER, topic, dedup, spam) | ❌ Chưa có |
| BI reports + InsightCard generator | ❌ Chưa có |
| Crisis detection | ❌ Chưa có |

## Danh sách tài liệu

### Plan (strategy + scope)

| File | Nội dung |
|---|---|
| `01_migration_scope_from_smap_analyse.md` | Scope, boundary, yêu cầu không được mất |
| `02_target_clean_architecture_python.md` | Architecture convention, folder structure target |
| `03_business_requirements_inventory.md` | Danh mục yêu cầu nghiệp vụ — **không thay đổi** |
| `04_core_porting_backlog.md` | Backlog theo phase (đã calibrate với thực tế) |
| `05_delivery_milestones.md` | Milestones và gate criteria |
| `06_risks_testing_cutover.md` | Risk register, test strategy, cutover plan — **vẫn valid** |

### Implement (execution guide)

| File | Phase | Critical path? |
|---|---|---|
| `implement/phase_1_contract_publisher.md` | Phase 1 — Wire contract topics | ✅ **Ưu tiên cao nhất** |
| `implement/phase_2_pipeline_skeleton.md` | Phase 2 — Orchestrator + run_id | ✅ |
| `implement/phase_3_ingestion_normalization.md` | Phase 3 — Port ingestion, normalize, dedup, spam | |
| `implement/phase_4_enrichment.md` | Phase 4 — Port entity NER, semantic ABSA, topic | |
| `implement/phase_5_reporting_insights.md` | Phase 5 — Port marts, BI reports, InsightCard | |
| `implement/phase_6_crisis_hardening.md` | Phase 6 — Crisis detection, outbox, observability | |

### Convention (reference, không thay đổi)

- `convention/convention_python.md` — **đây là convention active cho analysis-srv**
- `convention/domain_convention/` — Go conventions cho các service khác (tham khảo)

## Thứ tự đọc khi bắt đầu

1. `01` → `02` → `03` để hiểu scope + architecture + requirements
2. `05` để biết deadline và gates
3. `implement/phase_1_*` để bắt đầu code ngay
4. `04` để track tiến độ backlog

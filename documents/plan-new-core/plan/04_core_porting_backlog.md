# Core Integration Backlog

> **Updated:** 2026-04-09
> **Note:** Backlog đã được calibrate lại. `core-analysis` hoàn thiện — các items bên dưới là **port vào internal/ convention**, không phải viết mới từ đầu.

## Trạng thái nhanh

| Wave | Trạng thái | Notes |
|---|---|---|
| Wave 1 — Contract Publisher | ❌ Chưa làm | **Critical path — làm trước** |
| Wave 2 — Pipeline Orchestrator | ❌ Chưa làm | Dependency của Wave 1 (cần run_id) |
| Wave 3 — Processing Core | ❌ Chưa làm | Port từ core-analysis |
| Wave 4 — Enrichment Core | ❌ Chưa làm | Port từ core-analysis |
| Wave 5 — Analytics và Insights | ❌ Chưa làm | Port từ core-analysis |
| Wave 6 — Crisis và Hardening | ❌ Chưa làm | |

---

## Wave 1 — Contract Publisher (PRIORITY 1)

> Implement `internal/contract_publisher/` — đây là gap lớn nhất.
> Source: `contract.md v1.2` (spec), `core-analysis` outputs (data).

**Tasks:**

- `CP-01` Implement `build_batch_completed_payload()` — map InsightMessage list → `analytics.batch.completed` envelope
  - Source map: `SentimentFact` → `nlp.sentiment`, `AspectOpinionFact` → `nlp.aspects[]`, `EntityFact` → `nlp.entities[]`, `IssueSignalFact` → `nlp.issues[]`, `StanceFact` → `nlp.stance`, `IntentFact` → `nlp.intent`, `SourceInfluenceFact` → `business.influence_tier`
  - Phải tính `business.impact_score` và `business.impact.priority` (port từ `internal/impact_calculation/`)

- `CP-02` Implement `build_insights_published_payloads()` — map `InsightCard[]` → list of insight card Kafka messages
  - Source map: `InsightCard.insight_type/title/summary/confidence/supporting_metrics/evidence_references` → contract fields
  - Parse `InsightCard.time_window` string → `analysis_window_start` + `analysis_window_end`
  - Add `run_id`, `project_id`, `campaign_id`, `should_index` từ run context

- `CP-03` Implement `build_report_digest_payload()` — map `BIReportBundle` → `analytics.report.digest`
  - Source map: `SOVReport.entities[]` → `top_entities[]`, `BuzzReport.topic_buzz[]` → `top_topics[]`, `TopIssuesReport.top_issues[]` → `top_issues[]`
  - `top_topics[].salient_terms` từ `BuzzTopicRow.salient_terms`
  - `top_topics[].effective_mention_count` từ `BuzzTopicRow.effective_mention_count`
  - `top_topics[].growth_ratio_proxy` từ `BuzzTopicRow.growth_ratio_proxy`

- `CP-04` Implement `publish_in_required_order()` — enforce ordering: batch → insights × N → digest
  - Phải publish hết batch trước khi publish insight đầu tiên
  - Phải publish hết insights trước khi publish digest

**Acceptance:** knowledge-srv nhận và parse được cả 3 topics không lỗi schema.

---

## Wave 2 — Pipeline Orchestrator + Runtime

> Source: `core-analysis/src/smap/pipeline.py`, `run_manifest.py`, `core/settings.py`

**Tasks:**

- `PL-01` Implement `internal/pipeline/` orchestrator — `run_pipeline(batch_input, run_ctx)` → `PipelineRunResult`
  - Gọi từng stage theo thứ tự, collect timings
  - Dùng feature flags để enable/disable stages (dedup, spam, enrichment)

- `PL-02` Implement `internal/runtime/usecase/run_id.py` — `default_run_id()` → `"run-YYYYMMDDTHHMMSSz"`

- `PL-03` Implement `internal/runtime/usecase/enum_registry.py` — normalize enum values (platform uppercase/lowercase, sentiment labels, v.v.)

- `PL-04` Port `internal/runtime/usecase/run_manifest.py` — `build_run_manifest()`, `summarize_runtime_mode()`
  - Source: `core-analysis/src/smap/run_manifest.py` L150, L348

**Acceptance:** `run_id` format chuẩn, run manifest sinh ra đúng schema.

---

## Wave 3 — Processing Core

> Source: `core-analysis/src/smap/ingestion/`, `normalization/`, `dedup/`, `quality/`, `threads/`

**Tasks:**

- `IN-01` Port `internal/ingestion/` — `IngestedBatchBundle`, UAP schema adapter (`KafkaToIngestedBatchAdapter`)
- `NM-01` Port `internal/normalization/` — text normalize, language detection (fastText), `MentionRecord`
- `DD-01` Port `internal/dedup/` — MinHash LSH (datasketch), exact + near-dedup, `dedup_weight`
- `SP-01` Port `internal/spam/` — author inorganic scoring, burst detection, `author_suspicious`
- `TH-01` Port `internal/threads/` — thread builder từ parent_id/root_id, `ThreadBundle`

**Acceptance:** Sample batch 2000 docs → stable `silver/mentions.parquet`, dedup rate reasonable.

---

## Wave 4 — Enrichment Core

> Source: `core-analysis/src/smap/enrichers/`, `canonicalization/`, `ontology/`

**Tasks:**

- `EN-01` Port `internal/enrichment/entity/` — NER pipeline, alias lookup, entity canonicalization
- `EN-02` Port `internal/enrichment/semantic/` — ABSA (target sentiment), issue signal detection, stance
- `EN-03` Port `internal/enrichment/topic/` — topic classification, `reporting_status` pipeline
- `EN-04` Port `internal/enrichment/service.py` — `EnricherService` wiring all enrichers

**Acceptance:** `entity_facts.parquet`, `aspect_facts.parquet`, `issue_facts.parquet`, `topic_facts.parquet` sinh ra đúng trên sample domain.

---

## Wave 5 — Analytics và Insights

> Source: `core-analysis/src/smap/marts/`, `analytics/`, `bi/`, `insights/`

**Tasks:**

- `RP-01` Port `internal/reporting/marts/` — `MartBundle` (18 Polars DataFrames)
- `RP-02` Port `internal/reporting/metrics/` — `build_metrics()` → `metrics.json`
- `RP-03` Port `internal/reporting/bi/` — `BIReportBundle` (7 reports)
- `RP-04` Port `internal/reporting/insights/` — `generate_insights()` → `InsightCard[]`

**Acceptance:** `bi_reports.json` sinh đúng trên sample, `InsightCard[]` có đủ 7 insight types.

---

## Wave 6 — Crisis và Hardening

**Tasks:**

- `CR-01` Implement `internal/crisis/usecase/evaluate_rules.py` — đọc crisis config per project, evaluate triggers (keyword volume / sentiment spike / influencer burst)
- `CR-02` Implement `internal/contract_publisher/usecase/publish_project_crisis.py` — publish `project.crisis.detected`
- `RV-01` Implement `internal/review/` — review queue logic, PostgreSQL persistence
- `HD-01` Implement outbox pattern — transactional publish, retry với backoff, DLQ policy
- `HD-02` Replay tool theo `run_id` — tái publish artifacts đã có vào Kafka

**Acceptance:** WARNING/CRITICAL trigger đúng trên test scenarios, no data loss khi producer fail.

---

## Backlog metadata template

```
- Task ID: (theo mã ở trên, e.g. CP-01)
- Module: internal/<module_name>/
- Source reference (core-analysis path): src/smap/<path>
- Target module (analysis-srv path): internal/<path>
- Dependencies: (các Task IDs phải xong trước)
- Acceptance criteria:
- Test cases:
- Library phụ thuộc: (e.g. polars, datasketch, faiss-cpu)
```

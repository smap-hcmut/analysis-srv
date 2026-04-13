# Delivery Milestones

> **Updated:** 2026-04-09
> **Note:** Milestones đã được recalibrate. `core-analysis` pipeline hoàn thiện — timeline tập trung vào port + wire, không phải build from scratch.

## Vị trí hiện tại

Codebase đang ở đầu **Phase 1**:

- ✅ Kafka consumer + per-document NLP pipeline đang chạy production
- ❌ `internal/contract_publisher/` chưa có → knowledge-srv KHÔNG nhận được data
- ❌ `run_id`, batch orchestration, BI reports, InsightCard chưa có

---

## Phase 1 — Contract Publisher (1–2 tuần) ← **LÀM NGAY**

**Mục tiêu:** knowledge-srv nhận được data từ analysis-srv lần đầu tiên.

**Việc cần làm:**

- Implement `internal/contract_publisher/` với 3 payload builders (batch, insights, digest)
- Implement `internal/runtime/usecase/run_id.py` + enum_registry
- Implement `internal/pipeline/` orchestrator tối giản (chỉ cần đủ để collect facts và trigger publish)
- Wire với dữ liệu từ NLP pipeline hiện có (sentiment, aspect, intent, impact)
- Xóa/deprecate producer `smap.analytics.output`

**Gate Phase 1:**

- `analytics.batch.completed` schema validation pass (knowledge-srv không reject)
- `analytics.insights.published` × 7 messages được consume
- `analytics.report.digest` trigger NotebookLM export trên staging
- `run_id` consistent trong cả 3 topics của cùng 1 run

---

## Phase 2 — Pipeline Skeleton + Processing Core (2–3 tuần)

**Mục tiêu:** Pipeline batch đầy đủ, per-document facts chất lượng cao.

**Việc cần làm:**

- Port `internal/ingestion/` — `KafkaToIngestedBatchAdapter`
- Port `internal/normalization/` — fastText lang detect, `MentionRecord`
- Port `internal/dedup/` — MinHash LSH (datasketch), near-dedup
- Port `internal/spam/` — author inorganic scoring, burst detection
- Port `internal/threads/` — thread builder từ parent_id hierarchy

**Gate Phase 2:**

- Sample batch 2000 docs → stable silver artifacts (mentions, dedup clusters, threads)
- Dedup rate trên golden dataset trong expected range (< 5% false positive)
- Không có regression với knowledge contract (Phase 1 gate vẫn pass)

---

## Phase 3 — Enrichment Core (3–4 tuần)

**Mục tiêu:** Entity NER, ABSA, topic classification — đây là ML core của core-analysis.

**Việc cần làm:**

- Port `internal/enrichment/entity/` — NER + alias lookup + entity canonicalization
- Port `internal/enrichment/semantic/` — target sentiment, aspect opinions, issue signals, stance
- Port `internal/enrichment/topic/` — topic classification, reportability scoring
- Wire entities → `nlp.entities[]` trong contract payload

**Gate Phase 3:**

- `entity_facts`, `aspect_facts`, `issue_facts`, `topic_facts` Parquet đúng schema
- `nlp.entities[]` trong `analytics.batch.completed` non-empty trên sample với domain facial-cleanser
- `nlp.issues[]` populated cho documents có issue signals rõ ràng

---

## Phase 4 — Analytics và BI Reports (2–3 tuần)

**Mục tiêu:** Sinh `BIReportBundle` và `InsightCard[]` từ gold-layer facts.

**Việc cần làm:**

- Port `internal/reporting/marts/` — MartBundle (Polars DataFrames)
- Port `internal/reporting/bi/` — 7 BI reports (SOV, Buzz, EmergingTopics, TopIssues, ThreadControversy, CreatorSourceBreakdown)
- Port `internal/reporting/insights/` — `generate_insights()` → `InsightCard[]` 7 types
- Wire `InsightCard[]` → `analytics.insights.published` với đúng `supporting_metrics` per type

**Gate Phase 4:**

- `bi_reports.json` pass schema validation
- `analytics.insights.published` có đủ 7 insight types trên sample run
- `analytics.report.digest.top_topics[]` có `salient_terms`, `growth_ratio_proxy`, `effective_mention_count`

---

## Phase 5 — Crisis + Hardening (2 tuần)

**Mục tiêu:** Production-ready: crisis detection, outbox, observability, cutover prep.

**Việc cần làm:**

- Implement `internal/crisis/` — evaluate crisis rules per project config
- Implement `project.crisis.detected` publisher
- Implement outbox pattern — transactional publish cho 3 knowledge topics
- Implement replay tool theo `run_id`
- Soak test trên full-size batch (2000+ docs)
- Viết runbook + dashboard

**Gate Phase 5:**

- WARNING/CRITICAL trigger đúng trên crisis test scenarios
- Zero data loss khi Kafka producer tạm thời fail (outbox retry hoạt động)
- Soak test 5 consecutive runs không lỗi

---

## Shadow Cutover (sau Phase 5)

Theo plan trong `06_risks_testing_cutover.md`:

1. **Shadow mode (1 tuần):** Run new pipeline parallel với old, so sánh output — không publish production topics
2. **Canary (1–2 tuần):** Enable publish cho 1–2 pilot projects, monitor knowledge-srv ingestion quality
3. **Full cutover:** Route 100% traffic, disable old `smap.analytics.output` producer hoàn toàn

---

## Timeline tổng

| Phase | Thời gian ước tính | Deliverable chính |
|---|---|---|
| Phase 1 | 1–2 tuần | knowledge-srv nhận data lần đầu |
| Phase 2 | 2–3 tuần | Silver artifacts chất lượng cao |
| Phase 3 | 3–4 tuần | Full NLP enrichment |
| Phase 4 | 2–3 tuần | BI reports + InsightCard |
| Phase 5 | 2 tuần | Production ready |
| Shadow + Cutover | 2–3 tuần | Full cutover |
| **Total** | **~12–17 tuần** | |

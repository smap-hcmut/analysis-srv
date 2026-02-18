# MASTER PROPOSAL: Analysis Service Upgrade — Intelligence Engine

**Phiên bản:** 1.1
**Ngày tạo:** 17/02/2026
**Cập nhật:** 17/02/2026 — Review feedback #1
**Repo:** analysis-srv (Python)
**Tác giả:** Auto-generated from `refactor_plan/`

---

## 1. MỤC TIÊU TỔNG THỂ

Nâng cấp Analysis Service từ một "text-processor" đơn thuần thành một **Intelligence Engine** có khả năng:

1. **Unified Input (UAP):** Nhận dữ liệu từ mọi nguồn (Social Crawl, File Upload, Webhook) qua chuẩn UAP (Unified Analytics Protocol) thay vì Event Envelope hiện tại.
2. **Enriched Output:** Sinh ra output có cấu trúc nested, phong phú — tương thích với Knowledge Service và Qdrant Vector DB cho RAG.
3. **Context Awareness:** Sử dụng metadata project/entity để chọn AI model phù hợp theo ngữ cảnh.
4. **Metric History:** Hỗ trợ lưu trữ lịch sử biến động metric (time-series) song song với state hiện tại.

---

## 2. PHÂN TÍCH GAP: HIỆN TẠI vs MỤC TIÊU

### 2.1 Input Layer

| Khía cạnh       | Hiện tại                                                                            | Mục tiêu                                                                            |
| :-------------- | :---------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| Format          | Event Envelope (flat `payload.meta`, `payload.content`, `payload.interaction`)      | UAP v1.0 (nested `ingest`, `content`, `signals`, `context`, `raw`)                  |
| Queue           | `analytics.data.collected` (RabbitMQ: exchange `smap.events`, routing key `data.collected`) | `smap.collector.output` (Kafka topic, format UAP)                                                |
| Parser          | `json.loads` trực tiếp trong `AnalyticsHandler`                                     | `UAPParser` class riêng, validate `uap_version`, extract structured blocks          |
| Entity context  | Không có — chỉ có `brand_name`, `keyword`                                           | `ingest.entity` (entity_type, entity_name, brand) — dùng cho Dynamic Model Loading  |
| Source tracking | `platform` (string đơn giản)                                                        | `ingest.source` (source_id, source_type, account_ref) — truy vết chi tiết           |
| Batch info      | `job_id`, `batch_index`, `minio_path`                                               | `ingest.batch` (batch_id, mode, received_at) + `ingest.trace` (raw_ref, mapping_id) |
| Attachments     | Không hỗ trợ                                                                        | `content.attachments[]` (image/video OCR/Caption — future)                          |

### 2.2 Output Layer

| Khía cạnh   | Hiện tại                                                                                   | Mục tiêu                                                                                                                         |
| :---------- | :----------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| Destination | Chỉ ghi PostgreSQL (`schema_analyst.analyzed_posts`)                                       | PostgreSQL + Publish lên Kafka topic `smap.analytics.output` (Enriched Output) — Knowledge Service consume qua Kafka             |
| Format      | Flat DB record (columns riêng lẻ)                                                          | Nested JSON (project, identity, content, nlp, business, rag, provenance)                                                         |
| Sentiment   | `overall_sentiment`, `overall_sentiment_score`, `overall_confidence`                       | Thêm `sentiment_explanation`, `sentiment_confidence` chi tiết hơn                                                                |
| Aspects     | `aspects_breakdown` (JSONB đơn giản: label, score, confidence, mentions, keywords, rating) | Nested array với `aspect_display_name`, `mentions[].start_pos/end_pos`, `impact_score`, `explanation`                            |
| Risk        | `risk_level` (LOW/MEDIUM/HIGH/CRITICAL dựa trên impact_score)                              | `risk_level` + `risk_score` (float) + `risk_factors[]` (factor, severity, description) + `requires_attention`, `alert_triggered` |
| Engagement  | `view_count`, `like_count`, ... (raw passthrough)                                          | `engagement_score`, `virality_score`, `influence_score`, `reach_estimate` (calculated)                                           |
| Quality     | Không có                                                                                   | `content_quality_score`, `is_spam`, `is_bot`, `language`, `language_confidence`, `toxicity_score`, `is_toxic`                    |
| RAG support | Không có                                                                                   | Block `rag` (should_index, quality_gate, citation, vector_ref)                                                                   |
| Provenance  | `pipeline_version`, `model_version`                                                        | Block `provenance` (raw_ref, pipeline steps with model info + timestamps)                                                        |
| DB Schema   | `schema_analyst.analyzed_posts` (flat)                                                     | `analytics.post_analytics` (enriched, nhiều fields mới)                                                                          |

### 2.3 Business Logic

| Khía cạnh        | Hiện tại                                            | Mục tiêu                                                            |
| :--------------- | :-------------------------------------------------- | :------------------------------------------------------------------ |
| Engagement Score | Không tính — chỉ passthrough raw metrics            | Formula: `(likes*1 + comments*2 + shares*3) / views * 100`, cap 100 |
| Virality Score   | Không có                                            | `shares / (likes + comments + 1)`                                   |
| Risk Assessment  | Dựa trên `impact_score` + `sentiment` (4 levels)    | Multi-factor: sentiment + crisis keywords + virality amplifier      |
| Spam Detection   | `intent_classification` stage (SPAM/SEEDING → skip) | Thêm heuristic: text_length, word diversity, ads intent patterns    |
| Influence Score  | `is_kol` flag (followers ≥ 50k)                     | `influence_score = author_followers / 1_000_000 * engagement_score` |

### 2.4 Architecture

| Khía cạnh       | Hiện tại                                    | Mục tiêu                                                                         |
| :-------------- | :------------------------------------------ | :------------------------------------------------------------------------------- |
| Data flow       | RabbitMQ → Consumer → Pipeline → PostgreSQL | Kafka → Consumer → Pipeline → PostgreSQL + Kafka Producer → Knowledge Service |
| Output queue    | Không có                                    | Kafka topic `smap.analytics.output` (Enriched Output JSON, payload là array)     |
| Builder pattern | Không có — pipeline ghi trực tiếp vào DB    | `ResultBuilder` transform AnalyzedPost → EnrichedPayload trước khi publish       |
| Metric history  | UPSERT (chỉ giữ state cuối)                 | Dual-storage: UPSERT `analytic_records` + APPEND `metric_snapshots`              |

---

## 3. KẾ HOẠCH THỰC THI CHI TIẾT

### Phase 1: Input Layer Refactoring — UAP Parser

**Mục tiêu:** Chuyển từ Event Envelope sang UAP v1.0.

**Scope thay đổi:**

#### 3.1.1 Tạo UAP Type Definitions (System-level)

Tạo type definitions cho UAP schema trong `internal/model/uap.py` (system-level types). Bao gồm:

- `UAPRecord`: Root structure
- `UAPIngest`: project_id, entity, source, batch, trace
- `UAPContent`: doc_id, text, author, attachments
- `UAPSignals`: engagement metrics, geo

Tham chiếu: `refactor_plan/input-output/input/UAP_INPUT_SCHEMA.md`

#### 3.1.2 Tạo UAPParser

Tạo parser class để validate và parse UAP JSON:

- Validate `uap_version == "1.0"`
- Extract và validate từng block (ingest, content, signals)
- Return `UAPRecord` dataclass
- Raise `UAPValidationError` nếu invalid

#### 3.1.3 Cập nhật AnalyticsHandler

Thay thế logic parse Event Envelope bằng `UAPParser`:

- Parse UAP JSON thay vì Event Envelope
- Extract context từ `ingest` block
- Propagate UAP metadata xuống pipeline

#### 3.1.4 Cập nhật Analytics Input Type

Thêm UAP-related fields vào `Input` type:

- `entity`, `source`, `batch`, `signals`, `context`
- Giữ backward compatibility với fields cũ (deprecate dần)

### Phase 2: Output Layer Refactoring — Enriched Output + Kafka Publisher

**Mục tiêu:** Sinh Enriched Output JSON và publish lên Kafka topic mới. Knowledge Service và các service khác trong hệ thống sử dụng Kafka làm message broker chính — Analysis Service cần align với hệ thống bằng cách publish output qua Kafka thay vì RabbitMQ.

**Lưu ý quan trọng:** Output payload publish lên Kafka là **array** các enriched post (batch), không phải single object. Điều này tối ưu throughput và phù hợp với cách Knowledge Service consume.

#### 3.2.1 Tạo ResultBuilder

Tạo module `builder` để transform AnalyzedPost + UAP Input → Enriched Output JSON.

**System-level types:** `EnrichedOutput` và các nested types (NLPBlock, BusinessBlock, RAGBlock) đặt trong `internal/model/enriched_output.py` vì là output contract chung của system.

**Builder logic:**

- Map UAP Input fields → Enriched Output (project, identity, content)
- Map AI results → Enriched Output (nlp, business)
- Construct RAG block (should_index, quality_gate, citation, vector_ref)
- Construct provenance block (raw_ref, pipeline steps)

Tham chiếu: `refactor_plan/04_data_mapping.md`, `refactor_plan/input-output/ouput/output_example.json`

#### 3.2.2 Tạo Kafka Producer (Output)

Sử dụng `pkg/kafka/producer.py` (`KafkaProducer` + `IKafkaProducer`) đã có sẵn.

**Output payload format:** Array of enriched posts (batch)

```python
# Publish batch array to Kafka
await kafka_producer.send_json(
    topic="smap.analytics.output",
    value=[enriched_1, enriched_2, ...],  # Array
    key=project_id,
)
```

#### 3.2.3 Cập nhật Pipeline Flow

Sau khi pipeline hoàn thành và DB save:

1. Build enriched output từ UAP + AI result
2. Accumulate vào batch buffer
3. Publish batch khi đủ size (configurable: `batch_publish_size`)

#### 3.2.4 Cập nhật ConsumerRegistry (DI)

Inject dependencies:

- `ResultBuilder` vào `AnalyticsPipeline`
- `KafkaProducer` (từ `pkg/kafka`) vào `AnalyticsPipeline`
- Kafka config từ `config.yaml`

### Phase 3: Database Schema Migration

**Mục tiêu:** Migrate từ `schema_analyst.analyzed_posts` sang `analytics.post_analytics`.

#### 3.3.1 Schema mới: `analytics.post_analytics`

Tạo migration SQL dựa trên `refactor_plan/indexing_input_schema.md`:

**Thay đổi chính:**

- Schema: `schema_analyst` → `analytics`
- Table: `analyzed_posts` → `post_analytics`
- ID type: VARCHAR(255) → UUID
- Thêm columns: `sentiment_confidence`, `sentiment_explanation`, `risk_score`, `risk_factors`, `requires_attention`, `alert_triggered`, `engagement_score`, `virality_score`, `influence_score`, `reach_estimate`, `content_quality_score`, `is_bot`, `language`, `language_confidence`, `toxicity_score`, `is_toxic`, `uap_metadata`, `ingested_at`, `content_created_at`, `indexed_at`
- Indexes: GIN indexes cho JSONB columns (`aspects`, `uap_metadata`)

#### 3.3.2 Cập nhật ORM Model

Cập nhật `internal/model/analyzed_post.py` để match schema mới.

#### 3.3.3 Cập nhật Repository

Cập nhật queries và UPSERT logic trong repository layer.

#### 3.3.4 Metric History Table (Optional — Phase sau)

Tạo `analytics.metric_snapshots` cho time-series storage (theo `refactor_plan/input-output/METRIC_HISTORY_STRATEGY/brainstorm.md`).

### Phase 4: Business Logic Upgrade

**Mục tiêu:** Implement các formula tính toán mới theo `05_business_logic.md`.

#### 3.4.1 Engagement Score (Mới)

Implement `calculate_engagement_score()` trong impact calculation module:

- Formula: `(likes*1 + comments*2 + shares*3) / views * 100`, cap 100
- Handle edge cases: views=0, all zeros

#### 3.4.2 Virality Score (Mới)

Implement `calculate_virality_score()`:

- Formula: `shares / (likes + comments + 1)`

#### 3.4.3 Risk Assessment Engine (Nâng cấp)

Nâng cấp từ simple 4-level risk sang multi-factor risk:

- Sentiment score impact
- Crisis keywords matching (["scam", "lừa đảo", "cháy", "tai nạn", "tẩy chay"])
- Virality amplifier (nếu risk > threshold và virality cao → amplify)
- Output: `risk_level`, `risk_score`, `risk_factors[]` (factor, severity, description)

Tham chiếu: `refactor_plan/05_business_logic.md`

#### 3.4.4 Spam Detection (Mới)

Implement heuristic spam detection:

- Text length < 5
- Word diversity < 30%
- Ads keywords matching (["mua ngay", "giảm giá", "click link"])

#### 3.4.5 Influence Score (Mới)

Implement `calculate_influence_score()`:

- Formula: `(author_followers / 1_000_000) * engagement_score`

### Phase 5: Data Mapping Implementation

**Mục tiêu:** Implement chính xác logic mapping UAP Input → Enriched Output theo `04_data_mapping.md`.

#### 3.5.1 Direct Mapping (Identity & Metadata)

| UAP Input Field             | Enriched Output Field | Logic                                                 |
| :-------------------------- | :-------------------- | :---------------------------------------------------- |
| `event_id`                  | `id`                  | Dùng source event ID hoặc generate `analytics_{uuid}` |
| `ingest.project_id`         | `project_id`          | Direct copy                                           |
| `ingest.source.source_id`   | `source_id`           | Direct copy                                           |
| `ingest.source.source_type` | `platform`            | Lowercase (FACEBOOK → facebook)                       |
| `content.published_at`      | `content_created_at`  | Direct copy, ensure ISO8601                           |
| `ingest.batch.received_at`  | `ingested_at`         | Direct copy                                           |
| `content.text`              | `content`             | Direct copy                                           |

#### 3.5.2 UAP Metadata Aggregation

| Enriched Output Field      | Source                        | Note                |
| :------------------------- | :---------------------------- | :------------------ |
| `uap_metadata.author`      | `content.author.author_id`    |                     |
| `uap_metadata.author_name` | `content.author.display_name` |                     |
| `uap_metadata.engagement`  | `signals.engagement`          | Copy toàn bộ object |
| `uap_metadata.url`         | `content.url`                 |                     |
| `uap_metadata.geo`         | `signals.geo`                 |                     |

#### 3.5.3 Calculated Fields (AI + Logic)

| Output Field                                    | Source                                   |
| :---------------------------------------------- | :--------------------------------------- |
| `overall_sentiment` / `overall_sentiment_score` | PhoBERT model inference                  |
| `aspects`                                       | ABSA model extraction                    |
| `keywords`                                      | YAKE + spaCy NER                         |
| `risk_level` / `risk_score` / `risk_factors`    | `evaluate_risk()` — Phase 4              |
| `engagement_score`                              | `calculate_engagement_score()` — Phase 4 |
| `virality_score`                                | `calculate_virality_score()` — Phase 4   |
| `influence_score`                               | `calculate_influence_score()` — Phase 4  |
| `is_spam`                                       | `detect_spam()` — Phase 4                |

---

### Phase 6: Legacy Cleanup

**Mục tiêu:** Remove toàn bộ legacy schema, code, và queue sau khi verify schema mới hoạt động ổn định.

**Điều kiện tiên quyết:** Schema mới `analytics.post_analytics` đã chạy ổn định ≥ 2 tuần, không có incident.

#### 3.6.1 Database Cleanup

Tạo migration `004_drop_legacy_schema.sql`:

- DROP TABLE `schema_analyst.analyzed_posts`
- DROP SCHEMA `schema_analyst` (nếu không còn table nào khác)
- Backup trước khi chạy

#### 3.6.2 Code Cleanup

Remove legacy code:

- Event Envelope parsing logic
- Legacy field mappings trong presenters
- Deprecated fields trong types (`job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version`, `brand_name`, `keyword`)
- Legacy columns trong ORM model
- Legacy queue config trong `config.yaml`

#### 3.6.3 Infrastructure Cleanup

- Xóa queue `analytics.data.collected` trên RabbitMQ
- Xóa exchange bindings cũ
- Revoke quyền user trên `schema_analyst`
- Cập nhật monitoring/alerting rules

---

## 4. INFRASTRUCTURE CHANGES

### 4.1 Queue/Topic Topology

| Queue/Topic                     | Broker    | Direction | Format                            | Consumer                             |
| :------------------------------ | :-------- | :-------- | :-------------------------------- | :----------------------------------- |
| `smap.collector.output` (MỚI)   | **Kafka** | Input     | UAP v1.0 JSON                     | Analysis Service                     |
| `smap.analytics.output` (MỚI)   | **Kafka** | Output    | **Array** of Enriched Output JSON | Knowledge Service + các service khác |
| `analytics.data.collected` (CŨ) | RabbitMQ  | Input     | Event Envelope                    | Deprecate dần                        |

**Lý do dùng Kafka cho cả input và output:** 
- Collector Service đã migrate sang publish qua Kafka
- Knowledge Service và các downstream service trong hệ thống SMAP đều sử dụng Kafka
- Analysis Service align với ecosystem bằng cách sử dụng Kafka cho cả input và output
- Kafka provides better scalability, durability, và replay capability

**Output payload là array:**

```json
[
  { "enriched_version": "1.0", "event_id": "...", "project": {...}, ... },
  { "enriched_version": "1.0", "event_id": "...", "project": {...}, ... }
]
```

**Hành động:**

- Tạo Kafka topic `smap.analytics.output`
- Cấu hình Knowledge Service consume topic này
- Cập nhật `config/config.yaml` thêm Kafka consumer + producer config
- Giữ queue cũ `analytics.data.collected` trong giai đoạn chuyển tiếp (nếu cần rollback)

### 4.2 Config Changes

**File sửa:** `config/config.yaml`

```yaml
# Kafka configuration (Input + Output)
kafka:
  bootstrap_servers: "172.16.21.206:9092"
  
  # Consumer configuration (Input - UAP messages from Collector)
  consumer:
    group_id: "analytics-service"
    topics:
      - "smap.collector.output"
    auto_offset_reset: "earliest"
    enable_auto_commit: false
    max_poll_records: 10
  
  # Producer configuration (Output - Enriched analytics)
  producer:
    topic: "smap.analytics.output"
    acks: "all"
    compression_type: "gzip"
    enable_idempotence: true
    batch_publish_size: 10
    linger_ms: 100
```

---

## 5. FILE CHANGES SUMMARY

### 5.1 Files Mới (Tạo)

| File                                                          | Mục đích                                            |
| :------------------------------------------------------------ | :-------------------------------------------------- |
| `internal/model/uap.py`                                       | UAP dataclass definitions (system-level)            |
| `internal/model/enriched_output.py`                           | EnrichedOutput types (system-level output contract) |
| `internal/analytics/delivery/rabbitmq/consumer/uap_parser.py` | UAP JSON parser + validator                         |
| `internal/analytics/delivery/kafka/producer/new.py`           | Kafka producer factory                              |
| `internal/analytics/delivery/kafka/producer/producer.py`      | Enriched Output Kafka publisher (batch array)       |
| `internal/builder/__init__.py`                                | Builder module init                                 |
| `internal/builder/interface.py`                               | IResultBuilder protocol                             |
| `internal/builder/type.py`                                    | Builder-specific private types                      |
| `internal/builder/errors.py`                                  | Builder errors                                      |
| `internal/builder/usecase/__init__.py`                        | Builder usecase init                                |
| `internal/builder/usecase/new.py`                             | Builder factory                                     |
| `internal/builder/usecase/enriched_output.py`                 | Core build logic: UAP + AI Result → Enriched Output |
| `migration/002_create_post_analytics.sql`                     | New schema migration                                |
| `migration/003_create_metric_snapshots.sql`                   | Metric history table (optional)                     |
| `migration/004_drop_legacy_schema.sql`                        | Drop legacy `schema_analyst` (Phase cuối)           |

### 5.2 Files Sửa (Modify)

| File                                                               | Thay đổi                                               |
| :----------------------------------------------------------------- | :----------------------------------------------------- |
| `internal/analytics/type.py`                                       | Thêm UAP-related fields vào Input type                 |
| `internal/analytics/delivery/rabbitmq/consumer/handler.py`         | Dùng UAPParser thay vì parse trực tiếp                 |
| `internal/analytics/delivery/rabbitmq/consumer/presenters.py`      | Map UAP → Pipeline Input                               |
| `internal/analytics/usecase/usecase.py`                            | Thêm ResultBuilder + Kafka Producer sau DB save        |
| `internal/consumer/registry.py`                                    | Inject ResultBuilder, KafkaProducer vào pipeline       |
| `internal/model/analyzed_post.py`                                  | Cập nhật ORM model cho schema mới                      |
| `internal/analyzed_post/type.py`                                   | Cập nhật CreateInput/UpdateInput types                 |
| `internal/analyzed_post/repository/postgre/analyzed_post.py`       | Cập nhật queries cho schema mới                        |
| `internal/analyzed_post/repository/postgre/analyzed_post_query.py` | Cập nhật query builders                                |
| `internal/impact_calculation/usecase/impact_calculation.py`        | Thêm engagement_score, virality_score, risk engine mới |
| `internal/impact_calculation/type.py`                              | Thêm output types cho metrics mới                      |
| `internal/text_preprocessing/usecase/*.py`                         | Thêm spam detection logic                              |
| `config/config.yaml`                                               | Thêm output queue config, cập nhật input queue         |

### 5.3 Files Không Đổi

Các module sau giữ nguyên interface, chỉ cần đảm bảo output format compatible:

- `internal/sentiment_analysis/` — output sentiment vẫn tương thích
- `internal/keyword_extraction/` — output keywords vẫn tương thích
- `internal/intent_classification/` — output intent vẫn tương thích
- `pkg/rabbitmq/` — giữ nguyên cho input consumer
- `pkg/kafka/` — đã có sẵn `KafkaProducer`, `IKafkaProducer`, `send_json()`, `send_batch()` — sử dụng trực tiếp cho output

### 5.4 Files Xóa / Deprecate (Legacy Cleanup)

| File / Resource                                                                               | Hành động                                                                                                                                                           | Thời điểm                                 |
| :-------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------- |
| `schema_analyst.analyzed_posts` (DB table)                                                    | DROP TABLE sau khi verify schema mới hoạt động ổn                                                                                                                   | Phase cuối (sau 2 tuần verify)            |
| `schema_analyst` (DB schema)                                                                  | DROP SCHEMA nếu không còn table nào khác                                                                                                                            | Phase cuối                                |
| Queue `analytics.data.collected`                                                              | Disable trong config, sau đó xóa trên RabbitMQ                                                                                                                      | Sau khi Collector chuyển sang publish UAP |
| Legacy fields trong `internal/analytics/type.py`                                              | Remove deprecated fields (`job_id`, `batch_index`, `task_type`, `keyword_source`, `crawled_at`, `pipeline_version`, `brand_name`, `keyword` — thay bằng UAP blocks) | Phase 5                                   |
| Legacy columns trong `internal/model/analyzed_post.py`                                        | Remove sau khi migrate xong                                                                                                                                         | Phase cuối                                |
| `internal/analytics/delivery/rabbitmq/consumer/presenters.py` (legacy Event Envelope mapping) | Remove legacy mapping code, chỉ giữ UAP mapping                                                                                                                     | Phase 5                                   |

---

## 6. DATA FLOW MỚI (END-TO-END)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        NEW DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Collector/Crawler/File Upload                                       │
│     ↓ (UAP v1.0 JSON)                                                  │
│                                                                         │
│  2. Kafka Topic: smap.collector.output                                  │
│     ↓                                                                   │
│                                                                         │
│  3. ConsumerGroup (aiokafka)                                            │
│     ↓                                                                   │
│                                                                         │
│  4. AnalyticsHandler.handle()                                           │
│     ├── UAPParser.parse(raw_json) → UAPRecord                          │
│     ├── Validate uap_version                                            │
│     └── Extract content + context                                       │
│     ↓                                                                   │
│                                                                         │
│  5. AnalyticsPipeline.process(uap_record)                               │
│     ├── Stage 1: TextPreprocessing (clean + spam detect)                │
│     ├── Stage 2: IntentClassification (gatekeeping)                     │
│     ├── Stage 3: KeywordExtraction (YAKE + spaCy)                       │
│     ├── Stage 4: SentimentAnalysis (PhoBERT ONNX)                       │
│     ├── Stage 5: ImpactCalculation (engagement, virality, risk, influence)│
│     └── Build AnalyticsResult                                           │
│     ↓                                                                   │
│                                                                         │
│  6. Persistence: AnalyzedPostUseCase.create()                           │
│     → INSERT INTO analytics.post_analytics                              │
│     ↓                                                                   │
│                                                                         │
│  7. ResultBuilder.build(uap_record, analytics_result)                   │
│     → Transform to Enriched Output JSON                                 │
│     → Accumulate vào batch buffer                                       │
│     ↓                                                                   │
│                                                                         │
│  8. KafkaProducer.publish_batch([enriched_output, ...])                 │
│     → Publish ARRAY of enriched posts to Kafka topic                    │
│     → Topic: smap.analytics.output                                      │
│     ↓                                                                   │
│                                                                         │
│  9. Knowledge Service (Kafka consumer)                                  │
│     → Index vào Qdrant Vector DB                                        │
│     → Phục vụ RAG queries                                               │
│                                                                         │
│  10. Các downstream services khác (Kafka consumers)                     │
│      → Dashboard, Alert Service, Reporting, etc.                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. ENRICHED OUTPUT SCHEMA (TARGET — Chi tiết)

Đây là schema đầy đủ mà Analysis Service phải produce, tương thích với Knowledge Service indexing.

**Kafka message payload là ARRAY:**

```json
[
  {
    "enriched_version": "1.0",
    "event_id": "uuid",

    "project": {
      "project_id": "proj_xxx",
      "entity_type": "product",
      "entity_name": "VF8",
      "brand": "VinFast",
      "campaign_id": "campaign_xxx"
    },

    "identity": {
      "source_type": "FACEBOOK",
      "source_id": "src_fb_01",
      "doc_id": "fb_post_123",
      "doc_type": "post",
      "url": "https://...",
      "language": "vi",
      "published_at": "ISO8601",
      "ingested_at": "ISO8601",
      "author": {
        "author_id": "fb_user_abc",
        "display_name": "Nguyễn A",
        "author_type": "user"
      }
    },

    "content": {
      "text": "Original text...",
      "clean_text": "Cleaned text...",
      "summary": "AI-generated summary..."
    },

    "nlp": {
      "sentiment": {
        "label": "MIXED",
        "score": 0.15,
        "confidence": "HIGH",
        "explanation": "..."
      },
      "aspects": [
        {
          "aspect": "BATTERY",
          "polarity": "NEGATIVE",
          "confidence": 0.74,
          "evidence": "pin sụt nhanh"
        }
      ],
      "entities": [{ "type": "PRODUCT", "value": "VF8", "confidence": 0.92 }]
    },

    "business": {
      "impact": {
        "engagement": {
          "like_count": 120,
          "comment_count": 34,
          "share_count": 5,
          "view_count": 1111
        },
        "impact_score": 0.81,
        "priority": "HIGH"
      },
      "alerts": [
        {
          "alert_type": "NEGATIVE_BRAND_SIGNAL",
          "severity": "MEDIUM",
          "reason": "...",
          "suggested_action": "..."
        }
      ]
    },

    "rag": {
      "index": {
        "should_index": true,
        "quality_gate": {
          "min_length_ok": true,
          "has_aspect": true,
          "not_spam": true
        }
      },
      "citation": {
        "source": "Facebook",
        "title": "Facebook Post",
        "snippet": "First 100 chars...",
        "url": "https://...",
        "published_at": "ISO8601"
      },
      "vector_ref": {
        "provider": "qdrant",
        "collection": "proj_xxx",
        "point_id": "event_id"
      }
    },

    "provenance": {
      "raw_ref": "minio://raw/...",
      "pipeline": [
        { "step": "normalize_uap", "at": "ISO8601" },
        { "step": "sentiment_analysis", "model": "phobert-sentiment-v1" },
        { "step": "aspect_extraction", "model": "phobert-aspect-v1" },
        { "step": "embedding", "model": "text-embedding-3-large" }
      ]
    }
  }
]
```

---

## 8. TIMELINE & PHÂN BỔ CÔNG VIỆC

| Phase       | Nội dung                        | Ước lượng     | Dependencies                     |
| :---------- | :------------------------------ | :------------ | :------------------------------- |
| **Phase 1** | UAP Parser + Input Layer        | 3-4 ngày      | Không                            |
| **Phase 2** | ResultBuilder + Kafka Publisher | 3-4 ngày      | Phase 1                          |
| **Phase 3** | DB Schema Migration             | 2-3 ngày      | Không (có thể song song Phase 1) |
| **Phase 4** | Business Logic Upgrade          | 3-4 ngày      | Phase 1 (cần UAP signals)        |
| **Phase 5** | Data Mapping Integration        | 2-3 ngày      | Phase 1 + 2 + 4                  |
| **Phase 6** | Legacy Cleanup                  | 1-2 ngày      | Phase 5 + 2 tuần verify          |
| **Testing** | Unit + Integration tests        | 3-4 ngày      | Tất cả phases                    |
| **Tổng**    |                                 | **~3.5 tuần** |                                  |

### Execution Order (Đề xuất)

```
Week 1: Phase 1 (UAP Parser) + Phase 3 (DB Migration) — song song
Week 2: Phase 4 (Business Logic) + Phase 2 (ResultBuilder + Kafka Publisher)
Week 3: Phase 5 (Data Mapping Integration) + Testing + Verification
Week 4: Phase 6 (Legacy Cleanup) — sau 2 tuần verify schema mới ổn định
```

---

## 9. VERIFICATION CHECKLIST

### 9.1 Unit Tests

- [ ] `UAPParser` parse valid/invalid UAP JSON (crawl + csv + webhook)
- [ ] `ResultBuilder` output matches `output_example.json` structure
- [ ] `calculate_engagement_score()` với các edge cases (views=0, all zeros)
- [ ] `calculate_virality_score()` division safety
- [ ] `evaluate_risk()` với crisis keywords, extreme negative, viral spread
- [ ] `detect_spam()` với short text, repetitive text, ads text

### 9.2 Integration Tests

- [ ] Send UAP message (crawl) → Check DB record trong `analytics.post_analytics`
- [ ] Send UAP message (csv) → Check DB record
- [ ] Check Kafka topic `smap.analytics.output` nhận đúng **array** of Enriched Output JSON
- [ ] Mỗi element trong array validate against `indexing_input_schema.md`
- [ ] Knowledge Service consume batch thành công từ Kafka topic
- [ ] Batch size config hoạt động đúng (gom đủ N records rồi mới publish)

### 9.3 Legacy Cleanup Verification

- [ ] Schema mới `analytics.post_analytics` hoạt động ổn định ≥ 2 tuần
- [ ] Không còn service nào đọc/ghi `schema_analyst.analyzed_posts`
- [ ] DROP TABLE `schema_analyst.analyzed_posts` thành công
- [ ] DROP SCHEMA `schema_analyst` (nếu trống)
- [ ] Queue cũ `analytics.data.collected` đã disable và không còn message pending
- [ ] Legacy code (Event Envelope parser, old presenters) đã remove

### 9.4 Backward Compatibility (Giai đoạn chuyển tiếp)

- [ ] Queue cũ `analytics.data.collected` vẫn hoạt động trong giai đoạn chuyển tiếp
- [ ] DB cũ `schema_analyst.analyzed_posts` không bị ảnh hưởng
- [ ] Rollback plan: có thể switch về flow cũ bằng config flag

---

## 10. RISKS & MITIGATIONS

| Risk                                    | Impact | Mitigation                                                        |
| :-------------------------------------- | :----- | :---------------------------------------------------------------- |
| UAP format chưa ổn định từ Collector    | HIGH   | Validate `uap_version`, reject unknown versions, log warnings     |
| Knowledge Service chưa sẵn sàng consume | MEDIUM | Kafka topic buffer messages, retention policy giữ data            |
| DB migration downtime                   | MEDIUM | Tạo schema mới song song, không drop schema cũ ngay               |
| Breaking change cho downstream          | HIGH   | Versioned output (`enriched_version: "1.0"`), backward compatible |
| Performance impact từ thêm Kafka step   | LOW    | Async produce, batch publish, compression (gzip)                  |
| Kafka connectivity issues               | MEDIUM | Retry logic trong `pkg/kafka`, circuit breaker, fallback log      |
| Legacy cleanup quá sớm                  | HIGH   | Chỉ cleanup sau ≥ 2 tuần verify, có rollback migration script     |
| Dual-write period (cả schema cũ + mới)  | LOW    | Chấp nhận tạm thời, config flag để switch                         |

---

## 11. TÀI LIỆU THAM CHIẾU

| Tài liệu              | Đường dẫn                                                          | Mô tả                               |
| :-------------------- | :----------------------------------------------------------------- | :---------------------------------- |
| Architecture Overview | `refactor_plan/01_architecture_overview.md`                        | Kiến trúc tổng quan Before/After    |
| API Contract          | `refactor_plan/02_api_contract.md`                                 | Input/Output interface specs        |
| Migration Steps       | `refactor_plan/03_migration_steps.md`                              | Execution plan gốc                  |
| Data Mapping          | `refactor_plan/04_data_mapping.md`                                 | Field-by-field mapping UAP → Output |
| Business Logic        | `refactor_plan/05_business_logic.md`                               | Formulas & algorithms               |
| Indexing Schema       | `refactor_plan/indexing_input_schema.md`                           | Target DB schema chi tiết           |
| UAP Input Schema      | `refactor_plan/input-output/input/UAP_INPUT_SCHEMA.md`             | UAP v1.0 spec                       |
| Output Explain        | `refactor_plan/input-output/ouput/OUTPUT_EXPLAIN.md`               | Enriched Output business usage      |
| Metric History        | `refactor_plan/input-output/METRIC_HISTORY_STRATEGY/brainstorm.md` | Time-series storage strategy        |
| Current Status        | `documents/status.md`                                              | Implementation status hiện tại      |
| Current Input         | `documents/input_payload.md`                                       | Event Envelope format hiện tại      |
| Current Output        | `documents/output_payload.md`                                      | DB output format hiện tại           |
| DDD Convention        | `documents/convention/domain_convention/convention.md`             | Coding standards                    |

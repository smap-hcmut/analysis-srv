# SMAP Analytics Service — Analysis Document

## 1. Tổng quan

SMAP Analytics Service là một microservice event-driven, đóng vai trò **analytics engine** trong hệ thống SMAP. Service nhận dữ liệu bài viết mạng xã hội từ Kafka (UAP v1.0 format), chạy qua pipeline NLP 5 giai đoạn, lưu kết quả phân tích vào PostgreSQL, và publish enriched output lên Kafka cho Knowledge Service.

### Vai trò trong hệ thống

```
Collector Service
        │
        ▼
   Kafka (smap.collector.output)
   UAP v1.0 messages
        │
        ▼
   ┌─────────────────────────────────┐
   │   SMAP Analytics Service        │
   │   (Consumer → Pipeline → DB)    │
   └─────────────────────────────────┘
        │           │          │
        ▼           ▼          ▼
   PostgreSQL    Kafka      MinIO
   (analytics.   (smap.     (raw
    post_        analytics   refs)
    analytics)   .output)
```

Service hoạt động như một **Kafka consumer** — không expose REST API. Entry point duy nhất là consumer lắng nghe topic `smap.collector.output` (consumer group: `analytics-service`), nhận UAP v1.0 messages.

**Architecture Changes (Completed):**
- ✅ Input: Kafka topic `smap.collector.output` (UAP v1.0 format)
- ✅ Output: PostgreSQL `analytics.post_analytics` + Kafka `smap.analytics.output`
- ❌ Legacy: RabbitMQ queue `analytics.data.collected` (REMOVED)
- ❌ Legacy: PostgreSQL `schema_analyst.analyzed_posts` (REMOVED)

---

## 2. Business Logic

### 2.1 Luồng xử lý chính

1. **Message Reception**: Consumer nhận UAP v1.0 message từ Kafka topic `smap.collector.output`.
2. **Validation & Parsing**: `UAPParser` validate JSON, extract `UAPRecord` với nested blocks (ingest, content, signals, context).
3. **Pipeline Processing**: Chạy tuần tự qua 5 giai đoạn phân tích AI.
4. **Persistence**: Kết quả được lưu vào `analytics.post_analytics` qua async SQLAlchemy.
5. **Enriched Output**: Build enriched output từ UAP + AI results.
6. **Kafka Publish**: Publish batch array of enriched outputs lên topic `smap.analytics.output`.
7. **Commit**: Kafka offset được commit sau khi xử lý thành công.

### 2.2 Pipeline 5 giai đoạn

Mỗi giai đoạn có thể bật/tắt độc lập qua config:

#### Stage 1: Text Preprocessing

- Làm sạch và chuẩn hóa text từ UAP content block.
- Loại bỏ URL, emoji, normalize Unicode (NFKC).
- Chuyển đổi teencode tiếng Việt (ko → không, dc → được, ...).
- Phát hiện spam: text quá ngắn, low word diversity, ads keywords.
- Output: `clean_text`, `is_spam`, `spam_reasons`.

#### Stage 2: Intent Classification

- Phân loại ý định bài viết dựa trên regex pattern matching.
- 7 loại intent theo thứ tự ưu tiên:
  | Intent | Priority | Mô tả |
  |--------|----------|-------|
  | CRISIS | 10 | Tẩy chay, lừa đảo, phốt |
  | SEEDING | 9 | Quảng cáo ẩn (inbox giá, zalo, liên hệ mua) |
  | SPAM | 9 | Vay tiền, bán sim, tuyển dụng |
  | COMPLAINT | 7 | Phàn nàn, thất vọng, đừng mua |
  | LEAD | 5 | Hỏi giá, mua ở đâu, đặt cọc |
  | SUPPORT | 4 | Hỏi bảo hành, hướng dẫn sử dụng |
  | DISCUSSION | 1 | Thảo luận chung (default) |
- **Gatekeeping**: Nếu intent là SPAM hoặc SEEDING, `should_skip=true` → bỏ qua các stage AI tốn kém phía sau.

#### Stage 3: Keyword Extraction

- Trích xuất từ khóa và thực thể từ text.
- Hai nguồn:
  - **Dictionary matching** (DICT): So khớp với aspect dictionary (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL).
  - **AI extraction** (AI): Sử dụng YAKE (statistical) + spaCy NER (entity recognition).
- Mỗi keyword có: `keyword`, `aspect`, `score`, `source`.
- Giới hạn tối đa 30 keywords (configurable).

#### Stage 4: Sentiment Analysis

- Phân tích cảm xúc sử dụng PhoBERT (ONNX runtime) — model tiếng Việt.
- Output:
  - **Overall sentiment**: label (POSITIVE/NEGATIVE/NEUTRAL), score (-1.0 → 1.0), confidence (0.0 → 1.0).
  - **Aspect-based sentiment**: Phân tích cảm xúc theo từng aspect (dựa trên keywords từ Stage 3).
  - **Probabilities**: Phân phối xác suất cho 3 class.
- Context windowing: Cắt text xung quanh keyword (100 ký tự) để phân tích aspect chính xác hơn.
- Thresholds: positive ≥ 0.25, negative ≤ -0.25, còn lại là neutral.

#### Stage 5: Impact Calculation

- Tính điểm ảnh hưởng (0-100) dựa trên công thức:

```
EngagementScore = (likes×1 + comments×2 + shares×3) / views × 100
ViralityScore = shares / (likes + comments + 1)
InfluenceScore = (followers / 1M) × EngagementScore
RawImpact = EngagementScore × ReachScore × PlatformMultiplier × SentimentAmplifier
ImpactScore = normalized to 0-100
```

- **Platform multipliers**: TikTok=1.0, Facebook=1.2, YouTube=1.5, Instagram=1.1.
- **Sentiment amplifiers**: Negative=1.5, Neutral=1.0, Positive=1.1.
- **Risk Assessment** (Multi-factor):
  - Factor 1: Negative sentiment (score < -0.3)
  - Factor 2: Extreme negative (score < -0.7)
  - Factor 3: Crisis keywords (lừa đảo, tẩy chay, phốt, cháy nổ, etc.)
  - Factor 4: Virality amplifier (high virality × existing risk)
  - Output: `risk_level` (CRITICAL/HIGH/MEDIUM/LOW), `risk_score`, `risk_factors` array
- **Flags**:
  - `is_viral`: impact_score ≥ 70.
  - `is_kol`: followers ≥ 50,000.

### 2.3 Error Handling

- Lỗi xử lý được catch và log, record vẫn được lưu với `processing_status="error"`.
- Kafka consumer retry: configurable max 3 lần, exponential backoff.
- Graceful shutdown: SIGTERM/SIGINT → hoàn thành message đang xử lý trước khi tắt.

### 2.4 Data Mapping: UAP → Enriched Output

Pipeline maps UAP input blocks vào enriched output structure:

| UAP Block | Enriched Output Block | Mapping |
|-----------|----------------------|---------|
| `ingest.project_id` | `project.project_id` | Direct |
| `ingest.entity` | `project.entity_*` | Entity context |
| `ingest.source` | `identity.source_*` | Source identity |
| `content.doc_id` | `identity.doc_id` | Document ID |
| `content.text` | `content.text` | Original text |
| `content.author` | `identity.author` | Author info |
| `signals.engagement` | `business.impact.engagement` | Metrics |
| AI results | `nlp.*` | Sentiment, aspects, entities |
| AI results | `business.impact.*` | Impact scores, alerts |
| AI results | `rag.*` | Indexing decision, citation |

---

## 3. Kiến trúc Domain-Driven Design

```
internal/
├── analytics/           # Orchestrator — điều phối pipeline
│   ├── delivery/        # Infrastructure adapters
│   │   ├── uap/         # UAP parser & presenters
│   │   └── kafka/       # Kafka producer for enriched output
│   ├── usecase/         # Core business logic (AnalyticsPipeline)
│   ├── type.py          # Domain types (Input, Output, AnalyticsResult)
│   └── interface.py     # Contracts (IAnalyticsPipeline, IAnalyticsPublisher)
│
├── builder/             # ResultBuilder — UAP + AI → Enriched Output
│   ├── usecase/         # Build logic
│   ├── type.py          # BuildInput, BuildOutput
│   └── interface.py     # IResultBuilder
│
├── text_preprocessing/  # Stage 1 — Làm sạch text + spam detection
├── intent_classification/ # Stage 2 — Phân loại ý định
├── keyword_extraction/  # Stage 3 — Trích xuất từ khóa
├── sentiment_analysis/  # Stage 4 — Phân tích cảm xúc (PhoBERT)
├── impact_calculation/  # Stage 5 — Tính điểm ảnh hưởng + risk assessment
│
├── analyzed_post/       # Repository layer — CRUD cho post_analytics
│   ├── repository/      # PostgreSQL repository implementation
│   │   └── postgre/     # Postgres-specific implementation
│   └── usecase/         # Business logic cho persistence
│
├── consumer/            # Infrastructure — Kafka consumer server
│   ├── registry.py      # DI container — khởi tạo tất cả domain services
│   └── kafka_server.py  # Kafka consumer server lifecycle
│
└── model/               # SQLAlchemy ORM models + System types
    ├── post_analytics.py # PostAnalytics table (analytics.post_analytics)
    ├── uap.py           # UAP system types (UAPRecord, etc.)
    └── enriched_output.py # Enriched Output system types
```

### Dependency Flow

```
KafkaConsumerServer
  → ConsumerRegistry (DI)
    → AnalyticsHandler (delivery adapter)
      → UAPParser (parse UAP v1.0)
      → AnalyticsPipeline (orchestrator)
        → TextPreprocessing (spam detection)
        → IntentClassification
        → KeywordExtraction
        → SentimentAnalysis
        → ImpactCalculation (engagement, virality, influence, risk)
        → AnalyzedPostUseCase
          → AnalyzedPostRepository (PostgreSQL)
        → ResultBuilder (UAP + AI → Enriched Output)
        → AnalyticsPublisher (batch publish to Kafka)
```

---

## 4. Tech Stack

| Component          | Technology             | Vai trò                       |
| ------------------ | ---------------------- | ----------------------------- |
| Language           | Python 3.12+           | Backend                       |
| Package Manager    | uv                     | Dependencies                  |
| Message Queue      | Kafka (aiokafka)       | Event-driven consumer/producer |
| Database           | PostgreSQL 15+         | Lưu kết quả phân tích         |
| ORM                | SQLAlchemy 2.x (async) | Async persistence             |
| Cache              | Redis                  | Cache (optional)              |
| Object Storage     | MinIO                  | Raw data references           |
| Sentiment Model    | PhoBERT (ONNX Runtime) | Phân tích cảm xúc tiếng Việt  |
| Keyword Extraction | YAKE + spaCy           | Statistical keywords + NER    |
| Config             | YAML + env vars        | Viper-style config loader     |

---

## 5. Tính năng chính

- **Event-driven**: Consume UAP v1.0 từ Kafka topic `smap.collector.output`.
- **Modular pipeline**: Mỗi stage bật/tắt độc lập qua config.
- **Enriched Output**: Build structured output cho Knowledge Service indexing.
- **Batch Publishing**: Accumulate enriched outputs, publish array to Kafka.
- **Idempotency**: Xử lý dựa trên unique `source_id` + `doc_id`.
- **Graceful degradation**: Lỗi được log và persist với status="error", không mất dữ liệu.
- **Horizontal scaling**: Stateless design, scale bằng cách tăng consumer instances.
- **Vietnamese NLP**: PhoBERT ONNX cho sentiment, teencode normalization, Vietnamese regex patterns cho intent.
- **Multi-factor Risk Assessment**: Crisis keywords + sentiment + virality amplifier.
- **Spam Detection**: Heuristics-based (text length, word diversity, ads keywords).
- **Configurable**: YAML config với env var override cho mọi parameter.

---

## 6. Database Schema

### Current Schema: `analytics.post_analytics`

**Location:** `analytics` schema (PostgreSQL)

**Key Columns:**
- Identity: `id` (UUID), `project_id`, `source_id`
- Content: `content`, `content_created_at`, `ingested_at`, `platform`
- UAP Metadata: `uap_metadata` (JSONB) — author, engagement, url, hashtags
- Sentiment: `overall_sentiment`, `overall_sentiment_score`, `sentiment_confidence`
- ABSA: `aspects` (JSONB array)
- Keywords: `keywords` (TEXT array)
- Risk: `risk_level`, `risk_score`, `risk_factors` (JSONB), `requires_attention`
- Engagement: `engagement_score`, `virality_score`, `influence_score`, `reach_estimate`
- Quality: `is_spam`, `is_bot`, `language`, `toxicity_score`
- Processing: `primary_intent`, `impact_score`, `processing_time_ms`, `model_version`, `processing_status`
- Timestamps: `analyzed_at`, `indexed_at`, `created_at`, `updated_at`

**Indexes:**
- `idx_post_analytics_project` on `project_id`
- `idx_post_analytics_source` on `source_id`
- `idx_post_analytics_created` on `content_created_at`
- `idx_post_analytics_sentiment` on `overall_sentiment`
- `idx_post_analytics_risk` on `risk_level`
- `idx_post_analytics_platform` on `platform`
- `idx_post_analytics_attention` on `requires_attention` (partial index)
- `idx_post_analytics_analyzed` on `analyzed_at`
- GIN indexes on `aspects` and `uap_metadata` JSONB columns

---

## 7. Kafka Topics

### Input Topic: `smap.collector.output`

**Format:** UAP v1.0 (Unified Analytics Protocol)

**Message Structure:**
```json
{
  "uap_version": "1.0",
  "event_id": "uuid",
  "ingest": {
    "project_id": "proj_xxx",
    "entity": { "entity_type": "product", "entity_name": "VF8", "brand": "VinFast" },
    "source": { "source_id": "src_fb_01", "source_type": "FACEBOOK" },
    "batch": { "batch_id": "batch_xxx", "mode": "SCHEDULED_CRAWL", "received_at": "ISO8601" },
    "trace": { "raw_ref": "minio://raw/..." }
  },
  "content": {
    "doc_id": "fb_post_123",
    "doc_type": "post",
    "text": "Original text...",
    "url": "https://...",
    "published_at": "ISO8601",
    "author": { "author_id": "fb_user_abc", "display_name": "Nguyễn A" }
  },
  "signals": {
    "engagement": { "like_count": 120, "comment_count": 34, "share_count": 5, "view_count": 1111 }
  },
  "context": { "keywords_matched": ["VF8"], "campaign_id": "campaign_xxx" }
}
```

### Output Topic: `smap.analytics.output`

**Format:** Enriched Output v1.0 (ARRAY of objects)

**Message Structure:**
```json
[
  {
    "enriched_version": "1.0",
    "event_id": "uuid",
    "project": { "project_id": "proj_xxx", "entity_type": "product", "entity_name": "VF8", "brand": "VinFast" },
    "identity": {
      "source_type": "FACEBOOK",
      "source_id": "src_fb_01",
      "doc_id": "fb_post_123",
      "doc_type": "post",
      "url": "https://...",
      "published_at": "ISO8601",
      "author": { "author_id": "fb_user_abc", "display_name": "Nguyễn A" }
    },
    "content": { "text": "Original text...", "clean_text": "Cleaned text...", "summary": "" },
    "nlp": {
      "sentiment": { "label": "MIXED", "score": 0.15, "confidence": "HIGH" },
      "aspects": [
        { "aspect": "BATTERY", "polarity": "NEGATIVE", "confidence": 0.74, "evidence": "pin sụt nhanh" }
      ],
      "entities": []
    },
    "business": {
      "impact": {
        "engagement": { "like_count": 120, "comment_count": 34, "share_count": 5, "view_count": 1111 },
        "impact_score": 0.81,
        "priority": "HIGH"
      },
      "alerts": [
        { "alert_type": "NEGATIVE_BRAND_SIGNAL", "severity": "MEDIUM", "reason": "..." }
      ]
    },
    "rag": {
      "index": { "should_index": true, "quality_gate": { "min_length_ok": true, "has_aspect": true, "not_spam": true } },
      "citation": { "source": "Facebook", "title": "Facebook Post", "snippet": "First 100 chars...", "url": "https://..." },
      "vector_ref": { "provider": "qdrant", "collection": "proj_xxx", "point_id": "event_id" }
    },
    "provenance": {
      "raw_ref": "minio://raw/...",
      "pipeline": [
        { "step": "normalize_uap", "at": "ISO8601" },
        { "step": "sentiment_analysis", "model": "phobert-sentiment-v1" },
        { "step": "aspect_extraction", "model": "phobert-aspect-v1" }
      ]
    }
  }
]
```

**Batch Publishing:**
- Accumulate up to `batch_size` (default: 10) enriched outputs
- Publish as JSON array to Kafka
- Kafka key: `project_id` (for partition routing)
- Flush on batch full or shutdown

---

## 8. Configuration

### Kafka Configuration

```yaml
kafka:
  bootstrap_servers: "172.16.21.202:9094"
  consumer:
    group_id: "analytics-service"
    topics:
      - "smap.collector.output"
    auto_offset_reset: "earliest"
    enable_auto_commit: false
  producer:
    compression_type: "gzip"
    acks: "all"
    max_in_flight_requests: 5
```

### Pipeline Configuration

```yaml
analytics:
  model_version: "1.0.0"
  enable_preprocessing: true
  enable_intent_classification: true
  enable_keyword_extraction: true
  enable_sentiment_analysis: true
  enable_impact_calculation: true
  
  # Batch publishing
  batch_size: 10
  flush_interval_seconds: 5.0
```

---

## 9. Monitoring & Observability

### Key Metrics

- **Throughput**: Messages processed per second
- **Latency**: Processing time per message (ms)
- **Error Rate**: Failed messages / total messages
- **Kafka Lag**: Consumer lag on `smap.collector.output`
- **Database**: Insert latency, connection pool usage
- **AI Models**: Inference time per stage

### Logging

- Structured JSON logs
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Key log events:
  - Message received (event_id, source_id)
  - Pipeline stage completion (stage name, elapsed_ms)
  - Database insert (record id, status)
  - Kafka publish (batch size, topic)
  - Errors (exception type, message, stack trace)

---

## 10. Deployment

### Docker

```bash
# Build image
docker build -t smap-analytics:latest .

# Run container
docker run -d \
  --name analytics-service \
  -e CONFIG_PATH=/app/config/config.yaml \
  -v $(pwd)/config:/app/config \
  smap-analytics:latest
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: analytics-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: analytics-service
  template:
    metadata:
      labels:
        app: analytics-service
    spec:
      containers:
      - name: analytics
        image: smap-analytics:latest
        env:
        - name: CONFIG_PATH
          value: /app/config/config.yaml
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

### Scaling

- Horizontal: Increase replicas (Kafka consumer group handles partition assignment)
- Vertical: Increase memory for AI models (PhoBERT ONNX)
- Partitioning: Kafka topic partitions = max parallelism

---

## 11. Migration History

### Phase 1: UAP Parser (Completed)
- Implemented UAP v1.0 parser
- Added UAP system types
- Updated handler to parse UAP messages

### Phase 2: Kafka Publisher (Completed)
- Implemented ResultBuilder (UAP + AI → Enriched Output)
- Added Kafka producer for enriched output
- Batch publishing to `smap.analytics.output`

### Phase 3: Database Migration (Completed)
- Created new schema `analytics.post_analytics`
- Migrated from `schema_analyst.analyzed_posts`
- Updated repository layer

### Phase 4: Business Logic Upgrade (Completed)
- Added engagement_score, virality_score, influence_score calculations
- Implemented multi-factor risk assessment
- Added spam detection heuristics

### Phase 5: Data Mapping (Completed)
- Refactored pipeline to use UAP fields directly
- Updated presenters to map UAP → domain Input
- Removed legacy PostData/EventMetadata types

### Phase 6: Legacy Cleanup (Completed)
- Removed RabbitMQ consumer code
- Dropped legacy schema `schema_analyst.analyzed_posts`
- Removed Event Envelope parsing logic
- Updated documentation

---

## 12. References

- UAP Input Schema: `refactor_plan/input-output/input/UAP_INPUT_SCHEMA.md`
- Enriched Output Schema: `refactor_plan/input-output/ouput/output_example.json`
- Database Schema: `refactor_plan/indexing_input_schema.md`
- Data Mapping: `refactor_plan/04_data_mapping.md`
- Master Proposal: `documents/master-proposal.md`
- Phase Code Plans: `documents/phase1_code_plan.md` through `documents/phase6_code_plan.md`

# Service: SMAP Analytics Service

> **Template Version**: 1.0  
> **Last Updated**: 03/03/2026  
> **Status**: ✅ Production Ready

---

## 🎯 Business Context

### Chức năng chính

SMAP Analytics Service là một **Intelligence Engine** xử lý phân tích dữ liệu mạng xã hội theo thời gian thực. Service này nhận dữ liệu crawl từ các nền tảng social media (TikTok, Facebook, YouTube, Instagram) qua Kafka, chạy pipeline AI 5 giai đoạn để phân tích sentiment, intent, keywords, và impact, sau đó lưu kết quả vào PostgreSQL và publish enriched output lên Kafka để các service downstream (Knowledge Service, Dashboard, Alert Service) sử dụng.

**Giải quyết vấn đề:**
- Phân tích tự động hàng nghìn bài post mỗi ngày từ social media
- Đánh giá sentiment (tích cực/tiêu cực/trung lập) và aspect-based sentiment analysis
- Phát hiện crisis, spam, seeding, complaint để xử lý kịp thời
- Tính toán impact score, risk level, virality để ưu tiên xử lý
- Trích xuất keywords và entities cho RAG (Retrieval-Augmented Generation)

### Luồng xử lý

```
Kafka Input (smap.collector.output - UAP v1.0)
    → Parse & Validate UAP
    → Stage 1: Text Preprocessing (spam detection, normalization)
    → Stage 2: Intent Classification (CRISIS/SPAM/COMPLAINT/LEAD/SUPPORT/DISCUSSION)
    → Stage 3: Keyword Extraction (YAKE + spaCy NER + Aspect Mapping)
    → Stage 4: Sentiment Analysis (PhoBERT ONNX - Overall + ABSA)
    → Stage 5: Impact Calculation (engagement, virality, risk, influence)
    → Persist to PostgreSQL (schema_analysis.post_insight)
    → Build Enriched Output
    → Publish to Kafka (smap.analytics.output - batch array)
```


### Giá trị cốt lõi

**Tự động hóa phân tích quy mô lớn:**
- Xử lý hàng nghìn posts/ngày từ nhiều nền tảng social media
- Pipeline AI 5 giai đoạn chạy tự động, không cần can thiệp thủ công
- Async/await architecture đảm bảo throughput cao

**Phát hiện sớm crisis và risk:**
- Intent classification phát hiện CRISIS, COMPLAINT với độ ưu tiên cao
- Risk assessment engine đánh giá multi-factor (sentiment + keywords + virality)
- Alert system tự động trigger khi phát hiện risk cao

**Enriched data cho downstream services:**
- Output format chuẩn hóa (UAP + Enriched Output) cho Knowledge Service
- Hỗ trợ RAG với quality gate và citation metadata
- Kafka-based integration cho real-time processing

**Context-aware analysis:**
- Aspect-based sentiment analysis (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)
- Entity và brand tracking qua UAP metadata
- Platform-specific impact calculation (TikTok, Facebook, YouTube có weight khác nhau)

---

## 🛠 Technical Details

### Protocol & Architecture

- **Protocol**: Event-Driven (Kafka Consumer/Producer)
- **Pattern**: Clean Architecture + Domain-Driven Design (DDD)
- **Design**: Layered Architecture (Delivery → UseCase → Repository)
- **Message Format**: UAP v1.0 (Unified Analytics Protocol) - Input, Enriched Output JSON - Output

### Tech Stack

| Component         | Technology                  | Version | Purpose                                    |
| ----------------- | --------------------------- | ------- | ------------------------------------------ |
| Language          | Python                      | 3.12+   | Backend service                            |
| Package Manager   | uv                          | latest  | Fast dependency management                 |
| Message Queue     | Kafka (aiokafka)            | 0.11.0+ | Event-driven I/O (input + output)          |
| Database          | PostgreSQL                  | 15+     | Analyzed posts storage                     |
| ORM               | SQLAlchemy 2.x (async)      | 2.0.46+ | Async persistence with asyncpg driver      |
| Cache             | Redis                       | 7.1.1+  | Caching layer (optional)                   |
| Storage           | MinIO                       | 7.2.0+  | Batch raw data storage                     |
| Compression       | Zstandard (zstd)            | 0.23.0+ | Data compression                           |
| Sentiment Model   | PhoBERT (ONNX Runtime)      | -       | Vietnamese sentiment analysis              |
| Keyword Extractor | YAKE + spaCy (xx_ent_wiki_sm) | 3.7.0+  | Keyword extraction + NER                   |
| Logging           | loguru                      | 0.7.3+  | Structured logging                         |
| Config            | YAML + python-dotenv        | -       | Configuration management                   |


### Database Schema

#### PostgreSQL Tables

**1. schema_analysis.post_insight** - Bảng chính lưu trữ kết quả phân tích AI

```sql
CREATE TABLE schema_analysis.post_insight (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    source_id VARCHAR(255),
    
    -- Content
    content TEXT,
    content_created_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ,
    platform VARCHAR(50),
    uap_metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Sentiment Analysis
    overall_sentiment VARCHAR(20) NOT NULL DEFAULT 'NEUTRAL',
    overall_sentiment_score FLOAT NOT NULL DEFAULT 0.0,
    sentiment_confidence FLOAT NOT NULL DEFAULT 0.0,
    sentiment_explanation TEXT,
    
    -- Aspect-Based Sentiment Analysis (ABSA)
    aspects JSONB NOT NULL DEFAULT '[]',
    
    -- Keywords
    keywords TEXT[] NOT NULL DEFAULT '{}',
    
    -- Risk Assessment
    risk_level VARCHAR(20) NOT NULL DEFAULT 'LOW',
    risk_score FLOAT NOT NULL DEFAULT 0.0,
    risk_factors JSONB NOT NULL DEFAULT '[]',
    requires_attention BOOLEAN NOT NULL DEFAULT false,
    alert_triggered BOOLEAN NOT NULL DEFAULT false,
    
    -- Engagement Metrics (calculated)
    engagement_score FLOAT NOT NULL DEFAULT 0.0,
    virality_score FLOAT NOT NULL DEFAULT 0.0,
    influence_score FLOAT NOT NULL DEFAULT 0.0,
    reach_estimate INTEGER NOT NULL DEFAULT 0,
    
    -- Content Quality
    content_quality_score FLOAT NOT NULL DEFAULT 0.0,
    is_spam BOOLEAN NOT NULL DEFAULT false,
    is_bot BOOLEAN NOT NULL DEFAULT false,
    language VARCHAR(10),
    language_confidence FLOAT NOT NULL DEFAULT 0.0,
    toxicity_score FLOAT NOT NULL DEFAULT 0.0,
    is_toxic BOOLEAN NOT NULL DEFAULT false,
    
    -- Processing Metadata
    primary_intent VARCHAR(50) NOT NULL DEFAULT 'DISCUSSION',
    intent_confidence FLOAT NOT NULL DEFAULT 0.0,
    impact_score FLOAT NOT NULL DEFAULT 0.0,
    processing_time_ms INTEGER NOT NULL DEFAULT 0,
    model_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    processing_status VARCHAR(50) NOT NULL DEFAULT 'success',
    
    -- Timestamps
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_post_insight_project ON schema_analysis.post_insight(project_id);
CREATE INDEX idx_post_insight_source ON schema_analysis.post_insight(source_id);
CREATE INDEX idx_post_insight_created ON schema_analysis.post_insight(content_created_at);
CREATE INDEX idx_post_insight_sentiment ON schema_analysis.post_insight(overall_sentiment);
CREATE INDEX idx_post_insight_risk ON schema_analysis.post_insight(risk_level);
CREATE INDEX idx_post_insight_platform ON schema_analysis.post_insight(platform);
CREATE INDEX idx_post_insight_analyzed ON schema_analysis.post_insight(analyzed_at);
```

**Lưu ý:**
- `uap_metadata` JSONB chứa author info, engagement raw metrics, geo, url
- `aspects` JSONB array chứa aspect-based sentiment (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)
- `risk_factors` JSONB array chứa chi tiết các yếu tố risk (factor, severity, description)
- GIN indexes trên JSONB columns để query nhanh
- UPSERT logic: Nếu `source_id` đã tồn tại → UPDATE, nếu không → INSERT

---

## 📡 Message Formats

### Input: Kafka Topic `smap.collector.output` (UAP v1.0)

**Format**: JSON (UAP - Unified Analytics Protocol v1.0)

**Example**:

```json
{
  "uap_version": "1.0",
  "event_id": "evt_abc123",
  "ingest": {
    "project_id": "proj_uuid",
    "entity": {
      "entity_type": "product",
      "entity_name": "VF8",
      "brand": "VinFast"
    },
    "source": {
      "source_id": "src_123",
      "source_type": "TIKTOK",
      "account_ref": { "name": "vinfast_official", "id": "123456" }
    },
    "batch": {
      "batch_id": "batch_xyz",
      "mode": "SCHEDULED_CRAWL",
      "received_at": "2026-03-03T10:00:00Z"
    },
    "trace": {
      "raw_ref": "s3://crawl-results/raw/batch_xyz.json",
      "mapping_id": "mapping_001"
    }
  },
  "content": {
    "doc_id": "post_789",
    "doc_type": "post",
    "text": "VF8 chạy êm, thiết kế đẹp nhưng giá hơi cao",
    "published_at": "2026-03-03T09:30:00Z",
    "url": "https://tiktok.com/@user/video/123",
    "author": {
      "author_id": "user_456",
      "display_name": "Nguyễn Văn A",
      "username": "nguyenvana",
      "avatar_url": "https://...",
      "followers": 15000,
      "is_verified": false,
      "author_type": "user"
    },
    "attachments": []
  },
  "signals": {
    "engagement": {
      "views": 50000,
      "likes": 1200,
      "comments_count": 45,
      "shares": 30,
      "saves": 15
    },
    "geo": {
      "country": "VN",
      "city": "HCM"
    }
  },
  "context": {}
}
```

**Business Logic Flow**:
1. Validate `uap_version == "1.0"` (reject nếu không match)
2. Parse UAP blocks: `ingest`, `content`, `signals`
3. Extract text, author, engagement metrics
4. Pass vào 5-stage AI pipeline


### Output: Kafka Topic `smap.analytics.output` (Enriched Output - Batch Array)

**Format**: JSON Array (batch of enriched posts)

**Example**:

```json
[
  {
    "enriched_version": "1.0",
    "event_id": "evt_abc123",
    "project": {
      "project_id": "proj_uuid",
      "entity_type": "product",
      "entity_name": "VF8",
      "brand": "VinFast"
    },
    "identity": {
      "source_id": "src_123",
      "platform": "tiktok",
      "doc_id": "post_789",
      "url": "https://tiktok.com/@user/video/123"
    },
    "content": {
      "text": "VF8 chạy êm, thiết kế đẹp nhưng giá hơi cao",
      "content_created_at": "2026-03-03T09:30:00Z",
      "ingested_at": "2026-03-03T10:00:00Z",
      "language": "vi",
      "language_confidence": 0.98
    },
    "nlp": {
      "sentiment": {
        "overall": "POSITIVE",
        "score": 0.65,
        "confidence": 0.85,
        "explanation": "Positive về thiết kế và hiệu suất, nhưng có concern về giá"
      },
      "aspects": [
        {
          "aspect": "DESIGN",
          "aspect_display_name": "Thiết kế",
          "sentiment": "POSITIVE",
          "score": 0.8,
          "confidence": 0.9,
          "mentions": ["thiết kế đẹp"],
          "keywords": ["thiết kế", "đẹp"]
        },
        {
          "aspect": "PERFORMANCE",
          "aspect_display_name": "Hiệu suất",
          "sentiment": "POSITIVE",
          "score": 0.7,
          "confidence": 0.85,
          "mentions": ["chạy êm"],
          "keywords": ["chạy", "êm"]
        },
        {
          "aspect": "PRICE",
          "aspect_display_name": "Giá cả",
          "sentiment": "NEGATIVE",
          "score": -0.5,
          "confidence": 0.8,
          "mentions": ["giá hơi cao"],
          "keywords": ["giá", "cao"]
        }
      ],
      "keywords": ["VF8", "thiết kế", "giá", "chạy êm"],
      "intent": {
        "primary": "DISCUSSION",
        "confidence": 0.9
      }
    },
    "business": {
      "risk": {
        "level": "LOW",
        "score": 15.5,
        "factors": [],
        "requires_attention": false,
        "alert_triggered": false
      },
      "engagement": {
        "engagement_score": 45.2,
        "virality_score": 0.025,
        "influence_score": 67.8,
        "reach_estimate": 50000,
        "impact_score": 42.3
      },
      "quality": {
        "content_quality_score": 0.85,
        "is_spam": false,
        "is_bot": false,
        "toxicity_score": 0.05,
        "is_toxic": false
      },
      "author": {
        "is_kol": false,
        "is_verified": false,
        "followers": 15000
      }
    },
    "rag": {
      "should_index": true,
      "quality_gate": "PASS",
      "citation": {
        "author": "Nguyễn Văn A",
        "platform": "tiktok",
        "published_at": "2026-03-03T09:30:00Z",
        "url": "https://tiktok.com/@user/video/123"
      },
      "vector_ref": null
    },
    "provenance": {
      "raw_ref": "s3://crawl-results/raw/batch_xyz.json",
      "pipeline_version": "1.0.0",
      "model_version": "phobert-onnx-1.0",
      "processed_at": "2026-03-03T10:01:23Z",
      "processing_time_ms": 450
    }
  }
]
```

**Lưu ý:**
- Output là **array** (batch) chứa nhiều enriched posts
- Kafka key = `project_id` (để partition routing)
- Knowledge Service consume batch này để index vào Qdrant Vector DB
- Dashboard, Alert Service cũng consume topic này

---

## 🔗 Integration & Dependencies

### External Services

**1. Collector Service** (Upstream)

- **Method**: Kafka Topic `smap.collector.output`
- **Purpose**: Cung cấp raw crawl data từ social media platforms
- **Message Format**: UAP v1.0 JSON
- **Error Handling**: 
  - Invalid JSON → Log error và skip message (commit offset)
  - UAP validation failed → Log warning và skip
  - Transient errors → Retry với exponential backoff
- **SLA**: N/A (async event-driven)

**2. Knowledge Service** (Downstream)

- **Method**: Kafka Topic `smap.analytics.output` (consumer)
- **Purpose**: Index enriched analytics vào Qdrant Vector DB cho RAG
- **Message Format**: Enriched Output JSON Array (batch)
- **Integration**: Knowledge Service consume batch array, extract text + metadata, generate embeddings, index vào Qdrant
- **SLA**: N/A (async event-driven)

**3. Dashboard Service** (Downstream)

- **Method**: Kafka Topic `smap.analytics.output` (consumer)
- **Purpose**: Hiển thị real-time analytics trên dashboard
- **Integration**: Consume enriched output, aggregate metrics, update dashboard
- **SLA**: N/A (async event-driven)

**4. Alert Service** (Downstream)

- **Method**: Kafka Topic `smap.analytics.output` (consumer)
- **Purpose**: Trigger alerts khi phát hiện crisis, high risk posts
- **Integration**: Filter posts với `risk_level = CRITICAL` hoặc `alert_triggered = true`, gửi notification
- **SLA**: N/A (async event-driven)

### Infrastructure Dependencies

**Message Queue** (Kafka)

```
Input Topic: smap.collector.output
- Consumer Group: analytics-service
- Auto Offset Reset: earliest
- Enable Auto Commit: false (manual commit sau khi xử lý xong)
- Max Poll Records: 10

Output Topic: smap.analytics.output
- Producer Config:
  - Acks: all (đảm bảo durability)
  - Compression: gzip
  - Idempotence: true (tránh duplicate)
  - Batch Size: 10 posts
  - Linger MS: 100ms

Message Format:
- Input: UAP v1.0 JSON (single object)
- Output: Enriched Output JSON Array (batch)

Handler: AnalyticsKafkaHandler
- Parse UAP JSON
- Validate uap_version
- Extract content + context
- Call AnalyticsPipeline.process()
- Persist to PostgreSQL
- Build enriched output
- Publish batch to Kafka
- Commit offset
```

**Cache** (Redis)

```
Host: 172.16.21.200:6379
DB: 0
Password: [configured]
Max Connections: 50

Key Patterns:
- analytics:cache:[key] → Cached data (TTL: configurable)

Usage: Optional caching layer (hiện tại chưa sử dụng nhiều)
```

**Database** (PostgreSQL)

```
Host: 172.16.19.10:5432
Database: smap
Schema: schema_analysis
User: analysis_prod (runtime), analyst_master (migrations)

Connection Pool:
- Pool Size: 20
- Max Overflow: 10
- Driver: asyncpg (async)

Tables:
- schema_analysis.post_insight (main table)

Migrations:
- Managed via SQL scripts in migration/ folder
- Run: uv run python scripts/run_migration.py migration/003_create_post_insight.sql
```

**Storage** (MinIO)

```
Endpoint: 172.16.21.10:9000
Access Key: [configured]
Secret Key: [configured]
Secure: false (HTTP)

Buckets:
- crawl-results: Store raw crawl data (batch payloads)

Compression: Zstd (level 2, min size 1KB)

Usage: Store large batch payloads referenced by UAP trace.raw_ref
```

---

## 🎨 Key Features & Highlights

### 1. 5-Stage AI Pipeline

**Description**: Pipeline xử lý tuần tự 5 giai đoạn AI/NLP để phân tích toàn diện mỗi post

**Implementation**:

**Stage 1: Text Preprocessing**
- Spam detection (keywords, phone numbers, excessive hashtags)
- Text normalization (lowercase, remove special chars)
- Early exit nếu phát hiện spam (skip các stage sau)

**Stage 2: Intent Classification**
- Pattern matching với 7 intent categories: CRISIS (priority 1), SEEDING (2), SPAM (3), COMPLAINT (4), LEAD (5), SUPPORT (6), DISCUSSION (7)
- Config: `config/intent_patterns.yaml` (regex patterns)
- Gatekeeping: Skip processing nếu intent = SPAM hoặc SEEDING

**Stage 3: Keyword Extraction**
- Hybrid approach: Dictionary-based + AI-based (YAKE + spaCy NER)
- Aspect mapping: Map keywords vào 5 aspects (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)
- Config: `config/aspects_patterns.yaml`
- Fuzzy matching cho AI-extracted keywords

**Stage 4: Sentiment Analysis**
- PhoBERT ONNX model (Vietnamese sentiment)
- Overall sentiment: POSITIVE/NEGATIVE/NEUTRAL với score và confidence
- Aspect-Based Sentiment Analysis (ABSA): Sentiment cho từng aspect
- Context window: 100 characters around keyword

**Stage 5: Impact Calculation**
- Engagement Score: `(likes*1 + comments*2 + shares*3) / views * 100` (cap 100)
- Virality Score: `shares / (likes + comments + 1)`
- Influence Score: `(followers / 1M) * engagement_score`
- Risk Assessment: Multi-factor (sentiment + crisis keywords + virality amplifier)
- Platform multiplier: TikTok 1.0x, Facebook 1.2x, YouTube 1.5x, Instagram 1.1x
- Sentiment amplifier: Negative 1.5x, Neutral 1.0x, Positive 1.1x

**Benefits**:
- Phân tích toàn diện từ text preprocessing đến impact calculation
- Early exit optimization (skip processing cho spam/seeding)
- Configurable thresholds và weights
- Async/await non-blocking I/O

### 2. UAP (Unified Analytics Protocol) Integration

**Description**: Chuẩn hóa input format qua UAP v1.0 để tích hợp với toàn bộ hệ thống SMAP

**Implementation**:
- UAP Parser: Validate `uap_version`, parse nested blocks (ingest, content, signals, context)
- Type-safe dataclasses: `UAPRecord`, `UAPIngest`, `UAPContent`, `UAPSignals`
- Error handling: `ErrUAPValidation`, `ErrUAPVersionUnsupported`
- Backward compatibility: Reject legacy Event Envelope format

**Benefits**:
- Chuẩn hóa message format across services
- Entity và brand tracking qua `ingest.entity`
- Source traceability qua `ingest.source` và `ingest.trace`
- Batch metadata qua `ingest.batch`

### 3. Enriched Output với RAG Support

**Description**: Output format phong phú hỗ trợ Knowledge Service index vào Qdrant Vector DB

**Implementation**:
- ResultBuilder: Transform UAP + AI results → Enriched Output JSON
- RAG block: `should_index`, `quality_gate`, `citation`, `vector_ref`
- Provenance block: `raw_ref`, `pipeline_version`, `model_version`, `processed_at`
- Batch publishing: Accumulate posts vào buffer, publish batch array khi đủ size

**Benefits**:
- Hỗ trợ RAG queries với quality gate và citation
- Traceability: Track từ raw data đến enriched output
- Batch optimization: Giảm số lần publish Kafka

### 4. Multi-Factor Risk Assessment

**Description**: Đánh giá risk dựa trên nhiều yếu tố, không chỉ sentiment

**Implementation**:
- Sentiment impact: Negative sentiment → higher risk
- Crisis keywords matching: ["scam", "lừa đảo", "cháy", "tai nạn", "tẩy chay"]
- Virality amplifier: High virality + high risk → amplify risk score
- Risk factors array: Chi tiết từng factor (factor, severity, description)
- Risk levels: LOW, MEDIUM, HIGH, CRITICAL
- Alert triggering: `requires_attention`, `alert_triggered` flags

**Benefits**:
- Phát hiện crisis sớm
- Ưu tiên xử lý posts có risk cao
- Explainable risk assessment (risk_factors array)

### 5. Performance Optimizations

**Caching Strategy**:
- Redis caching layer (optional, chưa sử dụng nhiều)
- In-memory caching cho aspect dictionary và intent patterns

**Database Optimization**:
- Indexes trên project_id, source_id, sentiment, risk_level, platform, analyzed_at
- GIN indexes trên JSONB columns (aspects, uap_metadata)
- UPSERT logic: Nếu source_id đã tồn tại → UPDATE, nếu không → INSERT
- Connection pooling: 20 connections, 10 overflow

**Concurrency**:
- Async/await throughout (non-blocking I/O)
- aiokafka async consumer/producer
- asyncpg async PostgreSQL driver
- Parallel processing: Kafka consumer group cho horizontal scaling

**Connection Pooling**:
- PostgreSQL: 20 connections, 10 overflow
- Redis: 50 max connections
- Kafka: Configurable batch size và linger time

### 6. Reliability Features

**Retry Logic**:
- Kafka consumer: Manual offset commit sau khi xử lý xong
- Transient errors: Retry với exponential backoff (implicit trong aiokafka)
- Poison messages: Log error và skip (commit offset để move forward)

**Circuit Breaker**:
- Chưa implement (TODO)

**Graceful Degradation**:
- Spam detection: Skip processing nếu phát hiện spam
- Intent gatekeeping: Skip processing nếu intent = SPAM/SEEDING
- Empty text handling: Return neutral sentiment

**Health Checks**:
- PostgreSQL health check: `await db.health_check()`
- Redis health check: `await redis.health_check()`
- Kafka producer health: Check connection status

**Graceful Shutdown**:
- SIGTERM/SIGINT handlers
- Flush Kafka producer buffer
- Close database connections
- Commit pending offsets

---

## 🚧 Status & Roadmap

### ✅ Done (Implemented & Tested)

- [x] UAP v1.0 Parser - Parse và validate Unified Analytics Protocol
- [x] 5-Stage AI Pipeline - Text preprocessing, intent, keywords, sentiment, impact
- [x] PhoBERT ONNX Sentiment Analysis - Vietnamese sentiment với ONNX runtime
- [x] YAKE + spaCy Keyword Extraction - Hybrid dictionary + AI approach
- [x] Aspect-Based Sentiment Analysis (ABSA) - Sentiment cho 5 aspects
- [x] Multi-Factor Risk Assessment - Sentiment + crisis keywords + virality
- [x] Engagement Metrics Calculation - Engagement, virality, influence scores
- [x] PostgreSQL Persistence - schema_analysis.post_insight table
- [x] Kafka Consumer - Subscribe smap.collector.output (UAP input)
- [x] Kafka Producer - Publish smap.analytics.output (enriched output batch)
- [x] Enriched Output Builder - Transform UAP + AI results → Enriched JSON
- [x] Graceful Shutdown - SIGTERM/SIGINT handlers
- [x] Async/Await Architecture - Non-blocking I/O throughout
- [x] Configuration Management - YAML + env vars
- [x] Structured Logging - loguru với context fields
- [x] Docker Deployment - Dockerfile cho consumer service

### 🔄 In Progress

- [ ] Load Testing - Benchmark throughput và latency (Status: 30% complete)
- [ ] Monitoring Dashboard - Grafana dashboard cho metrics (Status: Planning)
- [ ] Alert Rules - Prometheus alerting rules (Status: Planning)

### 📋 Todo (Planned)

- [ ] Metric History Table - Time-series storage cho metric snapshots (Priority: Medium)
- [ ] Circuit Breaker - Implement circuit breaker cho external services (Priority: Medium)
- [ ] Rate Limiting - Rate limit per project_id (Priority: Low)
- [ ] API Layer - FastAPI health/metrics endpoints (Priority: Low)
- [ ] Toxicity Detection - Implement toxicity scoring (Priority: Medium)
- [ ] Language Detection - Auto-detect language với confidence (Priority: Medium)
- [ ] Bot Detection - Heuristic bot detection (Priority: Low)
- [ ] Content Quality Scoring - Implement content quality algorithm (Priority: Medium)
- [ ] Attachment Processing - OCR/Caption cho images/videos (Priority: Low)
- [ ] Dynamic Model Loading - Load model dựa trên entity context (Priority: Low)

### 🐛 Known Bugs

- [ ] Bug #001: Kafka producer buffer không flush khi service shutdown đột ngột (Severity: Medium, Workaround: Graceful shutdown với SIGTERM)
- [ ] Bug #002: PhoBERT ONNX inference chậm với text dài >512 tokens (Severity: Low, Workaround: Truncate text)

---

## ⚠️ Known Issues & Limitations

### 1. Performance - PhoBERT Inference Latency

**Issue**: PhoBERT ONNX inference mất ~100-200ms per text, bottleneck cho throughput

- **Current**: PhoBERT ONNX model chạy trên CPU, max length 256 tokens
- **Problem**: Với batch size lớn, inference time tăng tuyến tính
- **Impact**: Throughput giới hạn ~5-10 posts/second per consumer instance
- **Workaround**: Horizontal scaling với Kafka consumer group (nhiều instances)
- **TODO**: 
  - Optimize ONNX model (quantization, pruning)
  - Consider GPU inference cho production
  - Implement batch inference (process multiple texts cùng lúc)

**Code location**: `pkg/phobert_onnx/phobert_onnx.py`

```python
# ❌ Current implementation (sequential inference)
for text in texts:
    result = model.predict(text)  # ~100-200ms each

# ✅ Proposed solution (batch inference)
results = model.predict_batch(texts)  # ~200-300ms for 10 texts
```

### 2. Scalability - Single Consumer Instance

**Issue**: Hiện tại chỉ chạy 1 consumer instance, không tận dụng Kafka partitioning

- **Current**: 1 consumer instance subscribe toàn bộ partitions của topic
- **Problem**: Không scale horizontally, throughput bị giới hạn
- **Impact**: Với traffic cao (>1000 posts/minute), consumer lag tăng
- **Workaround**: Tăng `max_poll_records` để process nhiều messages per poll
- **TODO**: 
  - Deploy multiple consumer instances với cùng consumer group
  - Kafka sẽ auto-balance partitions across instances
  - Monitor consumer lag với Kafka metrics

**Code location**: `config/config.yaml`

```yaml
# ❌ Current config
kafka:
  consumer:
    max_poll_records: 10  # Too small for high traffic

# ✅ Proposed config
kafka:
  consumer:
    max_poll_records: 50  # Process more messages per poll
```

### 3. Error Handling - Poison Message Handling

**Issue**: Poison messages (invalid JSON, UAP validation failed) được skip và commit offset, không có retry mechanism

- **Current**: Log error và commit offset để move forward
- **Problem**: Mất data nếu message bị corrupt tạm thời (network issue)
- **Impact**: Data loss cho một số messages
- **Workaround**: Collector Service có retry logic trước khi publish
- **TODO**: 
  - Implement Dead Letter Queue (DLQ) cho poison messages
  - Retry transient errors với exponential backoff
  - Alert khi DLQ size vượt threshold

**Code location**: `internal/analytics/delivery/kafka/consumer/handler.py`

```python
# ❌ Current implementation
except json.JSONDecodeError as exc:
    logger.error(f"Invalid JSON: {exc}")
    return  # Skip message, commit offset

# ✅ Proposed solution
except json.JSONDecodeError as exc:
    logger.error(f"Invalid JSON: {exc}")
    await publish_to_dlq(message)  # Send to DLQ for manual review
    return
```

### 4. Monitoring - Lack of Metrics

**Issue**: Không có metrics export cho monitoring (Prometheus, Grafana)

- **Current**: Chỉ có structured logging với loguru
- **Problem**: Không track throughput, latency, error rate real-time
- **Impact**: Khó debug performance issues, không có alerting
- **Workaround**: Parse logs để extract metrics (không real-time)
- **TODO**: 
  - Implement Prometheus metrics exporter
  - Track: throughput (posts/sec), latency (p50/p95/p99), error rate, consumer lag
  - Setup Grafana dashboard
  - Configure Prometheus alerting rules

**Code location**: `apps/consumer/main.py`

```python
# ✅ Proposed solution
from prometheus_client import Counter, Histogram, Gauge

posts_processed = Counter('analytics_posts_processed_total', 'Total posts processed')
processing_latency = Histogram('analytics_processing_latency_seconds', 'Processing latency')
consumer_lag = Gauge('analytics_consumer_lag', 'Consumer lag')

# In handler
with processing_latency.time():
    await pipeline.process(input_data)
posts_processed.inc()
```

### 5. Configuration - Hardcoded Thresholds

**Issue**: Nhiều thresholds và weights hardcoded trong code, không configurable

- **Current**: Thresholds trong constant files (e.g., `VIRAL_THRESHOLD = 70.0`)
- **Problem**: Phải rebuild/redeploy để thay đổi thresholds
- **Impact**: Không flexible cho A/B testing, tuning
- **Workaround**: Edit config.yaml và restart service
- **TODO**: 
  - Move tất cả thresholds vào config.yaml
  - Support hot-reload config (không cần restart)
  - Implement feature flags cho A/B testing

**Code location**: `internal/impact_calculation/constant.py`

```python
# ❌ Current implementation
VIRAL_THRESHOLD = 70.0  # Hardcoded

# ✅ Proposed solution (in config.yaml)
impact:
  threshold:
    viral: 70.0  # Configurable
```

### 6. Testing - Low Test Coverage

**Issue**: Chưa có unit tests và integration tests đầy đủ

- **Current**: Chỉ có manual testing
- **Problem**: Khó refactor code, risk regression bugs
- **Impact**: Slow development velocity, bugs in production
- **Workaround**: Manual testing trước khi deploy
- **TODO**: 
  - Write unit tests cho từng module (target: 80% coverage)
  - Write integration tests cho end-to-end flow
  - Setup CI/CD pipeline với automated testing
  - Add property-based testing cho edge cases

**Code location**: `tests/` (chưa có)

```bash
# ✅ Proposed test structure
tests/
  unit/
    test_sentiment_analysis.py
    test_keyword_extraction.py
    test_impact_calculation.py
  integration/
    test_pipeline_e2e.py
    test_kafka_integration.py
```

---

## 🔮 Future Enhancements

### Short-term (1-2 months)

- [ ] **Prometheus Metrics Export** - Implement metrics exporter cho monitoring (throughput, latency, error rate, consumer lag)
- [ ] **Grafana Dashboard** - Setup dashboard cho real-time monitoring
- [ ] **Dead Letter Queue (DLQ)** - Implement DLQ cho poison messages
- [ ] **Load Testing** - Benchmark throughput và latency với realistic traffic
- [ ] **Unit Tests** - Write unit tests cho core modules (target: 80% coverage)
- [ ] **Integration Tests** - Write end-to-end tests cho pipeline flow

### Mid-term (3-6 months)

- [ ] **Batch Inference Optimization** - Implement batch inference cho PhoBERT để tăng throughput
- [ ] **Horizontal Scaling** - Deploy multiple consumer instances với Kafka consumer group
- [ ] **Metric History Table** - Implement time-series storage cho metric snapshots
- [ ] **Circuit Breaker** - Implement circuit breaker cho external services (PostgreSQL, Redis, MinIO)
- [ ] **Toxicity Detection** - Implement toxicity scoring model
- [ ] **Language Detection** - Auto-detect language với confidence score
- [ ] **Content Quality Scoring** - Implement algorithm đánh giá content quality

### Long-term (6+ months)

- [ ] **GPU Inference** - Migrate PhoBERT inference sang GPU cho production
- [ ] **Dynamic Model Loading** - Load model dựa trên entity context (e.g., model riêng cho automotive vs electronics)
- [ ] **Attachment Processing** - OCR/Caption cho images/videos
- [ ] **Real-time Dashboard API** - FastAPI endpoints cho health checks, metrics, manual triggers
- [ ] **A/B Testing Framework** - Feature flags và A/B testing cho thresholds tuning
- [ ] **Multi-language Support** - Support English, Chinese sentiment models
- [ ] **Advanced Risk Models** - ML-based risk prediction thay vì rule-based

---

## 🔧 Configuration

**File**: `config/config.yaml`

```yaml
# Database Configuration
database:
  url: "postgresql+asyncpg://analysis_prod:pwd@172.16.19.10:5432/smap"
  url_sync: "postgresql://analysis_prod:pwd@172.16.19.10:5432/smap"
  pool_size: 20
  max_overflow: 10

# Logging Configuration
logging:
  level: "INFO"
  debug: false

# Kafka Configuration
kafka:
  bootstrap_servers: "172.16.21.202:9094"
  topics:
    - "smap.collector.output"
  group_id: "analytics-service"

# Redis Configuration
redis:
  host: "172.16.21.200"
  port: 6379
  db: 0
  password: "21042004"
  max_connections: 50

# MinIO Configuration
minio:
  endpoint: "172.16.21.10:9000"
  access_key: "tantai"
  secret_key: "21042004"
  secure: false
  crawl_results_bucket: "crawl-results"

# Compression Configuration
compression:
  enabled: true
  default_level: 2
  min_size_bytes: 1024

# Text Preprocessing Configuration
preprocessor:
  min_text_length: 10
  max_comments: 5

# Intent Classification Configuration
intent_classifier:
  confidence_threshold: 0.5
  patterns_path: "config/intent_patterns.yaml"

# Impact Calculation Configuration
impact:
  weight:
    view: 0.01
    like: 1.0
    comment: 2.0
    save: 3.0
    share: 5.0
  platform:
    tiktok: 1.0
    facebook: 1.2
    youtube: 1.5
    instagram: 1.1
    unknown: 1.0
  amplifier:
    negative: 1.5
    neutral: 1.0
    positive: 1.1
  threshold:
    viral: 70.0
    kol_followers: 50000
    max_raw_score: 100000.0
```

**Environment Variables** (override config.yaml):

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/smap
KAFKA_BOOTSTRAP_SERVERS=172.16.21.202:9094
REDIS_HOST=172.16.21.200
REDIS_PASSWORD=xxx
MINIO_ENDPOINT=172.16.21.10:9000
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx

# Optional
LOG_LEVEL=INFO
KAFKA_GROUP_ID=analytics-service
KAFKA_TOPICS=smap.collector.output
```

---

## 📊 Performance Metrics

### Estimated Performance

**Note**: Đây là estimates dựa trên code analysis và initial testing, chưa có actual load tests với production traffic

**Processing Latency (per post)**:
- Text Preprocessing: ~5-10ms
- Intent Classification: ~5-10ms (regex matching)
- Keyword Extraction: ~50-100ms (YAKE + spaCy)
- Sentiment Analysis: ~100-200ms (PhoBERT ONNX inference - bottleneck)
- Impact Calculation: ~5-10ms
- Database Write: ~10-20ms
- Total: ~175-350ms per post

**Throughput**:
- Single consumer instance: ~3-5 posts/second (limited by PhoBERT inference)
- With 5 consumer instances: ~15-25 posts/second
- Target: >50 posts/second (cần optimize PhoBERT inference)

**Resource Usage** (per consumer instance):
- CPU: ~50-70% (PhoBERT inference intensive)
- Memory: ~1-2GB (PhoBERT model + spaCy model)
- Network: ~1-5 Mbps (Kafka I/O)

**Database Performance**:
- UPSERT latency: ~10-20ms
- Query latency (by project_id): ~5-10ms (indexed)
- Connection pool utilization: ~30-50%

**Kafka Performance**:
- Consumer lag: <100 messages (normal operation)
- Producer throughput: ~100 messages/second (batch publishing)
- Message size: ~5-10KB per enriched output

**TODO**: Run load tests để có accurate numbers với production-like traffic

---

## 🔐 Security

### Authentication

- **Method**: N/A (internal service, không expose public API)
- **Kafka**: SASL/PLAIN authentication (nếu configured)
- **PostgreSQL**: Username/password authentication
- **Redis**: Password authentication
- **MinIO**: Access key + secret key

### Authorization

- **Model**: N/A (internal service)
- **Database**: Role-based access control
  - `analyst_master`: DDL operations (CREATE, ALTER, DROP)
  - `analysis_prod`: DML operations (SELECT, INSERT, UPDATE, DELETE)

### Data Protection

- **Encryption at Rest**: PostgreSQL encryption (nếu configured)
- **Encryption in Transit**: 
  - Kafka: TLS (nếu configured)
  - PostgreSQL: SSL (nếu configured)
  - Redis: TLS (nếu configured)
- **PII Handling**: 
  - Author info (name, username) stored trong `uap_metadata` JSONB
  - Không store sensitive data (email, phone) trong analytics DB
- **Secrets Management**: Environment variables (TODO: migrate to Vault)

### Security Best Practices

- [x] Input validation (UAP parser validates structure)
- [x] SQL injection prevention (SQLAlchemy ORM, parameterized queries)
- [ ] XSS protection (N/A - không có web UI)
- [ ] CSRF protection (N/A - không có web UI)
- [ ] Rate limiting (TODO)
- [ ] API authentication (TODO - khi có API layer)
- [x] Audit logging (structured logging với loguru)
- [ ] Dependency scanning (TODO - setup Dependabot)
- [ ] Security headers (N/A - không có HTTP endpoints)

---

## 🧪 Testing

### Test Coverage

- **Unit Tests**: 0% coverage (TODO)
- **Integration Tests**: 0 scenarios (TODO)
- **E2E Tests**: 0 critical paths (TODO)
- **Load Tests**: Not completed (TODO)

### Running Tests

```bash
# Unit tests (TODO)
make test

# Integration tests (TODO)
make test-integration

# E2E tests (TODO)
make test-e2e

# Load tests (TODO)
make test-load

# Coverage report (TODO)
make coverage
```

### Test Strategy

**Unit Tests** (TODO):
- Test từng module riêng lẻ (sentiment, keyword, intent, impact)
- Mock external dependencies (PhoBERT model, spaCy, database)
- Test edge cases (empty text, invalid input, extreme values)

**Integration Tests** (TODO):
- Test end-to-end pipeline flow
- Test Kafka integration (consumer + producer)
- Test database integration (CRUD operations)
- Use testcontainers cho PostgreSQL, Redis, Kafka

**Mocking Strategy** (TODO):
- Mock PhoBERT model với fake predictions
- Mock spaCy model với fake NER results
- Mock Kafka producer/consumer với in-memory queue
- Mock database với SQLite in-memory

**Test Data** (TODO):
- Sample UAP messages với different scenarios
- Sample texts với different sentiments, intents, aspects
- Edge cases: empty text, very long text, special characters

---

## 🚀 Deployment

### Docker

**Dockerfile**: `apps/consumer/Dockerfile`

```bash
# Build
docker build -t smap-analytics:latest -f apps/consumer/Dockerfile .

# Run
docker run -d \
  --name analytics-consumer \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/smap" \
  -e KAFKA_BOOTSTRAP_SERVERS="172.16.21.202:9094" \
  -e REDIS_HOST="172.16.21.200" \
  -e REDIS_PASSWORD="xxx" \
  -e MINIO_ENDPOINT="172.16.21.10:9000" \
  -e MINIO_ACCESS_KEY="xxx" \
  -e MINIO_SECRET_KEY="xxx" \
  -e LOG_LEVEL="INFO" \
  smap-analytics:latest

# View logs
docker logs -f analytics-consumer

# Stop
docker stop analytics-consumer
```

### Kubernetes (TODO)

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: analytics-consumer
  namespace: smap
spec:
  replicas: 3  # Horizontal scaling
  selector:
    matchLabels:
      app: analytics-consumer
  template:
    metadata:
      labels:
        app: analytics-consumer
    spec:
      containers:
      - name: analytics-consumer
        image: smap-analytics:latest
        ports:
        - containerPort: 8080  # Health check port (TODO)
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: analytics-secrets
              key: database-url
        - name: KAFKA_BOOTSTRAP_SERVERS
          valueFrom:
            configMapKeyRef:
              name: analytics-config
              key: kafka-bootstrap-servers
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
```

### CI/CD Pipeline (TODO)

```yaml
# .github/workflows/deploy.yml
name: Deploy Analytics Service
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run tests
        run: make test
      - name: Run linters
        run: make lint
  
  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build Docker image
        run: docker build -t smap-analytics:${{ github.sha }} -f apps/consumer/Dockerfile .
      - name: Push to registry
        run: docker push smap-analytics:${{ github.sha }}
  
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/analytics-consumer \
            analytics-consumer=smap-analytics:${{ github.sha }} \
            -n smap
```

### Local Development

```bash
# 1. Clone repository
git clone <repository-url>
cd analysis-srv

# 2. Install dependencies
make install

# 3. Download SpaCy model
make spacy-model

# 4. Copy and edit config
cp config/config.example.yaml config/config.yaml
# Edit database URL, Kafka bootstrap servers, Redis, MinIO

# 5. Setup database
# Create schema
psql -h localhost -U postgres -d smap -c "CREATE SCHEMA IF NOT EXISTS schema_analysis;"

# Run migration
uv run python scripts/run_migration.py migration/003_create_post_insight.sql

# 6. Run consumer service
make run-consumer

# 7. Test
curl http://localhost:8080/health  # TODO: Implement health endpoint
```

---

## 📚 Documentation

### API Documentation

- **Swagger/OpenAPI**: N/A (chưa có API layer)
- **Postman Collection**: N/A
- **API Examples**: N/A

### Architecture Docs

- **System Design**: `documents/master-proposal.md` - Master proposal cho upgrade plan
- **Database Schema**: `migration/003_create_post_insight.sql` - Schema definition
- **UAP Specification**: `documents/input_payload.md` - UAP v1.0 format
- **Enriched Output Spec**: `documents/output_payload.md` - Enriched output format
- **Phase Plans**: `documents/phase{1-5}_code_plan.md` - Implementation plans

### Developer Guides

- **Setup Guide**: `README.md` - Quick start và setup instructions
- **Contributing Guide**: N/A (TODO)
- **Code Style Guide**: N/A (TODO - follow PEP 8)
- **Domain Conventions**: `documents/convention/domain_convention/` - Domain-driven design conventions

---

## 📞 Contact & Support

### Team

- **Service Owner**: SMAP Analytics Team
- **Tech Lead**: [Name]
- **On-call**: #smap-analytics Slack channel

### Resources

- **Repository**: [GitHub/GitLab URL]
- **Issue Tracker**: [Jira/GitHub Issues URL]
- **Monitoring**: [Grafana dashboard URL] (TODO)
- **Logs**: [Kibana/CloudWatch URL] (TODO)
- **Slack Channel**: #smap-analytics

### SLA & Support

- **Availability Target**: 99.9% (TODO: Define SLA)
- **Response Time**: 
  - P0 (Service down): 15 minutes
  - P1 (Critical bug): 1 hour
  - P2 (Major bug): 4 hours
  - P3 (Minor bug): 1 day
- **Support Hours**: 24/7 (on-call rotation)

---

## 📝 Changelog

### [1.0.0] - 2026-03-03

**Added**
- UAP v1.0 Parser - Parse và validate Unified Analytics Protocol
- 5-Stage AI Pipeline - Text preprocessing, intent classification, keyword extraction, sentiment analysis, impact calculation
- PhoBERT ONNX Sentiment Analysis - Vietnamese sentiment model với ONNX runtime
- YAKE + spaCy Keyword Extraction - Hybrid dictionary + AI approach
- Aspect-Based Sentiment Analysis (ABSA) - Sentiment cho 5 aspects (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)
- Multi-Factor Risk Assessment - Sentiment + crisis keywords + virality amplifier
- Engagement Metrics Calculation - Engagement score, virality score, influence score
- PostgreSQL Persistence - schema_analysis.post_insight table
- Kafka Consumer - Subscribe smap.collector.output (UAP input)
- Kafka Producer - Publish smap.analytics.output (enriched output batch)
- Enriched Output Builder - Transform UAP + AI results → Enriched JSON
- Graceful Shutdown - SIGTERM/SIGINT handlers
- Async/Await Architecture - Non-blocking I/O throughout
- Configuration Management - YAML + environment variables
- Structured Logging - loguru với context fields
- Docker Deployment - Dockerfile cho consumer service

**Changed**
- Migrated from RabbitMQ to Kafka for message queue
- Migrated from Event Envelope to UAP v1.0 format
- Migrated from schema_analyst.analyzed_posts to schema_analysis.post_insight

**Fixed**
- N/A (initial release)

**Deprecated**
- Event Envelope format (replaced by UAP v1.0)
- RabbitMQ queue analytics.data.collected (replaced by Kafka topic smap.collector.output)
- Legacy schema schema_analyst.analyzed_posts (replaced by schema_analysis.post_insight)

**Removed**
- N/A (initial release)

**Security**
- Added input validation với UAP parser
- Added SQL injection prevention với SQLAlchemy ORM

---

## 🎓 Learning Resources

### Internal Docs

- **Master Proposal**: `documents/master-proposal.md` - Comprehensive upgrade plan
- **Phase Plans**: `documents/phase{1-5}_code_plan.md` - Detailed implementation plans
- **Domain Conventions**: `documents/convention/domain_convention/` - DDD conventions
- **Analysis Document**: `documents/analysis.md` - System analysis

### External Resources

**Python & Async**
- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [SQLAlchemy 2.0 async tutorial](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

**Kafka**
- [aiokafka documentation](https://aiokafka.readthedocs.io/)
- [Kafka consumer best practices](https://kafka.apache.org/documentation/#consumerconfigs)

**NLP & ML**
- [PhoBERT paper](https://arxiv.org/abs/2003.00744) - Vietnamese BERT model
- [YAKE keyword extraction](https://github.com/LIAAD/yake)
- [spaCy documentation](https://spacy.io/usage)
- [ONNX Runtime](https://onnxruntime.ai/)

**Domain-Driven Design**
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## 📋 Appendix

### Glossary

- **UAP**: Unified Analytics Protocol - Chuẩn message format chung cho SMAP system
- **ABSA**: Aspect-Based Sentiment Analysis - Phân tích sentiment theo từng aspect
- **NER**: Named Entity Recognition - Trích xuất entities từ text
- **YAKE**: Yet Another Keyword Extractor - Algorithm trích xuất keywords
- **PhoBERT**: Vietnamese BERT model - Pre-trained language model cho tiếng Việt
- **ONNX**: Open Neural Network Exchange - Format chuẩn cho ML models
- **DDD**: Domain-Driven Design - Software design approach
- **RAG**: Retrieval-Augmented Generation - AI technique kết hợp retrieval và generation
- **KOL**: Key Opinion Leader - Người có ảnh hưởng lớn trên social media
- **DLQ**: Dead Letter Queue - Queue lưu messages không xử lý được

### Related Services

- **Collector Service**: Crawl data từ social media platforms, publish UAP messages lên Kafka
- **Knowledge Service**: Index enriched analytics vào Qdrant Vector DB, phục vụ RAG queries
- **Dashboard Service**: Hiển thị real-time analytics trên web dashboard
- **Alert Service**: Trigger alerts khi phát hiện crisis, high risk posts

### Migration Guides

- **Event Envelope → UAP v1.0**: `documents/master-proposal.md` - Section 3.1
- **schema_analyst → schema_analysis**: `migration/003_create_post_insight.sql`
- **RabbitMQ → Kafka**: `documents/master-proposal.md` - Section 4.1

---

**Document Version**: 1.0  
**Last Updated**: 03/03/2026  
**Maintained By**: SMAP Analytics Team  
**Review Cycle**: Monthly

---

## 📌 Quick Reference Card

```
Service: SMAP Analytics Service
Type: Kafka Consumer (Event-Driven)
Port: N/A (no HTTP endpoints yet)
Health: N/A (TODO: Implement /health endpoint)
Metrics: N/A (TODO: Implement Prometheus metrics)

Quick Start:
1. Clone repo: git clone <repo-url>
2. Install deps: make install
3. Download SpaCy model: make spacy-model
4. Copy config: cp config/config.example.yaml config/config.yaml
5. Edit config: vim config/config.yaml
6. Run migration: uv run python scripts/run_migration.py migration/003_create_post_insight.sql
7. Run consumer: make run-consumer
8. Check logs: tail -f logs/analytics.log

Common Commands:
- Start: make run-consumer
- Test: make test (TODO)
- Lint: make lint
- Format: make format
- Clean: make clean
- Build Docker: docker build -t smap-analytics:latest -f apps/consumer/Dockerfile .

Configuration:
- Config file: config/config.yaml
- Env vars: DATABASE_URL, KAFKA_BOOTSTRAP_SERVERS, REDIS_HOST, etc.
- Intent patterns: config/intent_patterns.yaml
- Aspect patterns: config/aspects_patterns.yaml

Key Directories:
- apps/consumer/ - Consumer service entry point
- internal/analytics/ - Core analytics pipeline
- internal/sentiment_analysis/ - PhoBERT sentiment analysis
- internal/keyword_extraction/ - YAKE + spaCy keyword extraction
- internal/intent_classification/ - Intent classification
- internal/impact_calculation/ - Impact & risk calculation
- internal/post_insight/ - PostgreSQL repository
- pkg/ - Shared packages (kafka, postgre, logger, phobert, spacy_yake)
- config/ - Configuration files
- migration/ - Database migrations

Kafka Topics:
- Input: smap.collector.output (UAP v1.0)
- Output: smap.analytics.output (Enriched Output batch array)

Database:
- Schema: schema_analysis
- Table: post_insight
- User: analysis_prod (runtime), analyst_master (migrations)

Emergency Contacts:
- On-call: #smap-analytics Slack channel
- Escalation: [Tech Lead Name]
- PagerDuty: [PagerDuty link]

Monitoring:
- Logs: [Kibana URL] (TODO)
- Metrics: [Grafana URL] (TODO)
- Alerts: [Prometheus Alertmanager URL] (TODO)

Troubleshooting:
- Consumer lag high: Check PhoBERT inference latency, scale horizontally
- Database connection errors: Check connection pool size, verify credentials
- Kafka connection errors: Check bootstrap servers, verify network connectivity
- Out of memory: Check PhoBERT model size, increase container memory limit
```

---

**END OF REPORT**

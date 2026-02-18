# Output Payload — SMAP Analysis Service

## Tổng quan

Sau khi xử lý qua pipeline 5 giai đoạn, Analysis Service tạo ra 2 loại output:

1. **Database**: Persist vào table `analytics.post_analytics` trong PostgreSQL
2. **Kafka**: Publish enriched output (batch array) lên topic `smap.analytics.output` cho Knowledge Service

---

## 1. Database Output

### 1.1 Database Target

- **Schema**: `schema_analysis`
- **Table**: `post_insight`
- **Primary Key**: `id` (UUID)
- **ORM**: SQLAlchemy 2.x async

### 1.2 Table Structure

Table `schema_analysis.post_insight` chứa kết quả phân tích đầy đủ với 50+ columns được nhóm theo các categories:

#### Core Identity
- `id` (UUID) - Primary key, định danh duy nhất của record analytics
- `project_id` (VARCHAR) - ID của project sở hữu data
- `source_id` (VARCHAR) - ID của data source

#### Content & Timestamps
- `content` (TEXT) - Nội dung text gốc cần phân tích
- `content_created_at` (TIMESTAMP) - Thời điểm nội dung được tạo bởi tác giả
- `ingested_at` (TIMESTAMP) - Thời điểm hệ thống nhận dữ liệu
- `platform` (VARCHAR) - Platform nguồn (facebook, tiktok, youtube, etc.)

#### UAP Metadata
- `uap_metadata` (JSONB) - Metadata từ UAP input (author, engagement, url, etc.)

#### Sentiment Analysis
- `overall_sentiment` (VARCHAR) - POSITIVE, NEGATIVE, NEUTRAL, MIXED
- `overall_sentiment_score` (FLOAT) - Điểm sentiment (-1 to 1)
- `sentiment_confidence` (FLOAT) - Độ tin cậy (0-1)
- `sentiment_explanation` (TEXT) - Giải thích sentiment (future)

#### Aspect-Based Sentiment
- `aspects` (JSONB) - Array of aspects với polarity, confidence, evidence

#### Keywords & Intent
- `keywords` (TEXT[]) - Array of extracted keywords
- `primary_intent` (VARCHAR) - DISCUSSION, QUESTION, COMPLAINT, PRAISE, SPAM, SEEDING
- `intent_confidence` (FLOAT) - Độ tin cậy intent classification

#### Risk Assessment
- `risk_level` (VARCHAR) - LOW, MEDIUM, HIGH, CRITICAL
- `risk_score` (FLOAT) - Điểm risk (0-1)
- `risk_factors` (JSONB) - Array of risk factors với severity và description
- `requires_attention` (BOOLEAN) - Flag cần xử lý ngay
- `alert_triggered` (BOOLEAN) - Flag đã trigger alert

#### Engagement & Impact
- `engagement_score` (FLOAT) - Điểm engagement (0-100)
- `virality_score` (FLOAT) - Điểm viral (0+)
- `influence_score` (FLOAT) - Điểm influence (0+)
- `reach_estimate` (INT) - Ước tính reach
- `impact_score` (FLOAT) - Điểm impact tổng hợp (0-100)

#### Content Quality
- `content_quality_score` (FLOAT) - Điểm chất lượng nội dung (future)
- `is_spam` (BOOLEAN) - Flag spam detection
- `is_bot` (BOOLEAN) - Flag bot detection (future)
- `language` (VARCHAR) - Ngôn ngữ (vi, en, etc.) (future)
- `language_confidence` (FLOAT) - Độ tin cậy language detection (future)
- `toxicity_score` (FLOAT) - Điểm toxic (future)
- `is_toxic` (BOOLEAN) - Flag toxic content (future)

#### Processing Metadata
- `processing_time_ms` (INT) - Thời gian xử lý (milliseconds)
- `model_version` (VARCHAR) - Version của AI models
- `processing_status` (VARCHAR) - success, error, skipped
- `analyzed_at` (TIMESTAMP) - Thời điểm phân tích hoàn thành
- `indexed_at` (TIMESTAMP) - Thời điểm index vào vector DB
- `created_at` (TIMESTAMP) - Thời điểm tạo record
- `updated_at` (TIMESTAMP) - Thời điểm update record

### 1.3 Example Database Record

```json
{
  "id": "analytics_550e8400-e29b-41d4-a716-446655440000",
  "project_id": "proj_vf8_monitor_01",
  "source_id": "src_fb_01",
  
  "content": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng.",
  "content_created_at": "2026-02-07T09:55:00Z",
  "ingested_at": "2026-02-07T10:00:00Z",
  "platform": "facebook",
  
  "uap_metadata": {
    "author": "fb_user_abc",
    "author_name": "Nguyễn A",
    "engagement": {
      "like_count": 120,
      "comment_count": 34,
      "share_count": 5,
      "view_count": 1111
    },
    "url": "https://facebook.com/.../posts/987654321"
  },
  
  "overall_sentiment": "NEGATIVE",
  "overall_sentiment_score": -0.45,
  "sentiment_confidence": 0.78,
  "sentiment_explanation": null,
  
  "aspects": [
    {
      "aspect": "BATTERY",
      "polarity": "NEGATIVE",
      "confidence": 0.74,
      "evidence": "pin sụt nhanh"
    },
    {
      "aspect": "PRICE",
      "polarity": "NEGATIVE",
      "confidence": 0.71,
      "evidence": "giá hơi cao"
    }
  ],
  
  "keywords": ["xe", "pin", "giá", "vf8"],
  "primary_intent": "COMPLAINT",
  "intent_confidence": 0.82,
  
  "risk_level": "MEDIUM",
  "risk_score": 0.55,
  "risk_factors": [
    {
      "factor": "NEGATIVE_SENTIMENT",
      "severity": "MEDIUM",
      "description": "Negative sentiment detected (score: -0.45)"
    }
  ],
  "requires_attention": false,
  "alert_triggered": false,
  
  "engagement_score": 45.2,
  "virality_score": 0.08,
  "influence_score": 12.5,
  "reach_estimate": 1111,
  "impact_score": 68.5,
  
  "content_quality_score": 0.0,
  "is_spam": false,
  "is_bot": false,
  "language": null,
  "language_confidence": 0.0,
  "toxicity_score": 0.0,
  "is_toxic": false,
  
  "processing_time_ms": 1250,
  "model_version": "1.0.0",
  "processing_status": "success",
  "analyzed_at": "2026-02-07T10:00:05Z",
  "indexed_at": null,
  "created_at": "2026-02-07T10:00:05Z",
  "updated_at": "2026-02-07T10:00:05Z"
}
```

### 1.4 Indexes

```sql
-- Primary key
CREATE UNIQUE INDEX idx_post_insight_pkey ON schema_analysis.post_insight(id);

-- Query optimization
CREATE INDEX idx_post_insight_project ON schema_analysis.post_insight(project_id);
CREATE INDEX idx_post_insight_platform ON schema_analysis.post_insight(platform);
CREATE INDEX idx_post_insight_created ON schema_analysis.post_insight(content_created_at DESC);
CREATE INDEX idx_post_insight_analyzed ON schema_analysis.post_insight(analyzed_at DESC);
CREATE INDEX idx_post_insight_sentiment ON schema_analysis.post_insight(overall_sentiment);
CREATE INDEX idx_post_insight_risk ON schema_analysis.post_insight(risk_level);

-- JSONB indexes
CREATE INDEX idx_post_insight_aspects_gin ON schema_analysis.post_insight USING GIN(aspects);
CREATE INDEX idx_post_insight_uap_gin ON schema_analysis.post_insight USING GIN(uap_metadata);
CREATE INDEX idx_post_insight_risk_factors_gin ON schema_analysis.post_insight USING GIN(risk_factors);

-- Composite indexes
CREATE INDEX idx_post_insight_project_created ON schema_analysis.post_insight(project_id, content_created_at DESC);
CREATE INDEX idx_post_insight_project_sentiment ON schema_analysis.post_insight(project_id, overall_sentiment);
```

---

## 2. Kafka Output (Enriched Output)

### 2.1 Kafka Target

- **Topic**: `smap.analytics.output`
- **Format**: JSON array (batch)
- **Consumer**: Knowledge Service + downstream services
- **Compression**: gzip

### 2.2 Enriched Output Structure

Enriched Output là format JSON được publish lên Kafka, có cấu trúc nested rõ ràng hơn DB schema:

```jsonc
{
  "enriched_version": "1.0",      // Version của enriched format
  "event_id": "uuid",             // ID của event gốc
  
  "project": { ... },             // Project context
  "identity": { ... },            // Document identity
  "content": { ... },             // Content blocks
  "nlp": { ... },                 // NLP analysis results
  "business": { ... },            // Business metrics & alerts
  "rag": { ... },                 // RAG indexing metadata
  "provenance": { ... }           // Processing provenance
}
```

### 2.3 Enriched Output Blocks

#### Block: `project`

```json
"project": {
  "project_id": "proj_vf8_monitor_01",
  "entity_type": "product",
  "entity_name": "VF8",
  "brand": "VinFast",
  "campaign_id": "id_feb_campaign_2026_01"
}
```

#### Block: `identity`

```json
"identity": {
  "source_type": "FACEBOOK",
  "source_id": "src_fb_01",
  "doc_id": "fb_post_987654321",
  "doc_type": "post",
  "url": "https://facebook.com/.../posts/987654321",
  "language": "vi",
  "published_at": "2026-02-07T09:55:00Z",
  "ingested_at": "2026-02-07T10:00:00Z",
  "author": {
    "author_id": "fb_user_abc",
    "display_name": "Nguyễn A",
    "author_type": "user"
  }
}
```

#### Block: `content`

```json
"content": {
  "text": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng.",
  "clean_text": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao so với kỳ vọng.",
  "summary": "Người dùng khen xe êm nhưng phàn nàn pin tụt nhanh và giá cao."
}
```

#### Block: `nlp`

```json
"nlp": {
  "sentiment": {
    "label": "NEGATIVE",
    "score": -0.45,
    "confidence": "HIGH",
    "explanation": "Nội dung chứa nhiều cụm từ phàn nàn về pin và giá."
  },
  "aspects": [
    {
      "aspect": "BATTERY",
      "polarity": "NEGATIVE",
      "confidence": 0.74,
      "evidence": "pin sụt nhanh"
    },
    {
      "aspect": "PRICE",
      "polarity": "NEGATIVE",
      "confidence": 0.71,
      "evidence": "giá hơi cao"
    }
  ],
  "entities": [
    { "type": "PRODUCT", "value": "VF8", "confidence": 0.92 }
  ]
}
```

#### Block: `business`

```json
"business": {
  "impact": {
    "engagement": {
      "like_count": 120,
      "comment_count": 34,
      "share_count": 5,
      "view_count": 1111
    },
    "engagement_score": 45.2,
    "virality_score": 0.08,
    "influence_score": 12.5,
    "impact_score": 68.5,
    "priority": "HIGH"
  },
  "alerts": [
    {
      "alert_type": "NEGATIVE_BRAND_SIGNAL",
      "severity": "MEDIUM",
      "reason": "Bài viết có sentiment NEGATIVE và lượng tương tác cao.",
      "suggested_action": "Theo dõi thêm các comment liên quan đến pin và giá."
    }
  ]
}
```

#### Block: `rag`

```json
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
    "snippet": "Xe đi êm nhưng pin sụt nhanh, giá hơi cao...",
    "url": "https://facebook.com/.../posts/987654321",
    "published_at": "2026-02-07T09:55:00Z"
  },
  "vector_ref": {
    "provider": "qdrant",
    "collection": "proj_vf8_monitor_01",
    "point_id": "b6d6b1e2-9cf3-4e69-8fd0-5b1c8aab9f17"
  }
}
```

#### Block: `provenance`

```json
"provenance": {
  "raw_ref": "minio://raw/proj_vf8_monitor_01/facebook/2026-02-07/batch_001.jsonl",
  "pipeline": [
    { "step": "normalize_uap", "at": "2026-02-07T10:00:30Z" },
    { "step": "sentiment_analysis", "model": "phobert-sentiment-v1", "at": "2026-02-07T10:00:32Z" },
    { "step": "aspect_extraction", "model": "phobert-aspect-v1", "at": "2026-02-07T10:00:34Z" },
    { "step": "embedding", "model": "text-embedding-3-large", "at": "2026-02-07T10:00:36Z" }
  ]
}
```

### 2.4 Batch Publishing

Kafka output được publish dưới dạng **array** (batch) để tối ưu throughput:

```json
[
  {
    "enriched_version": "1.0",
    "event_id": "uuid-1",
    "project": { ... },
    ...
  },
  {
    "enriched_version": "1.0",
    "event_id": "uuid-2",
    "project": { ... },
    ...
  }
]
```

**Configuration:**

```yaml
kafka:
  producer:
    topic: "smap.analytics.output"
    batch_publish_size: 10  # Gom 10 records rồi publish
    linger_ms: 100
    compression_type: "gzip"
```

---

## 3. Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Analytics Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. UAP Input (from RabbitMQ)                               │
│     ↓                                                       │
│  2. Text Preprocessing                                      │
│     ↓                                                       │
│  3. Intent Classification                                   │
│     ↓                                                       │
│  4. Keyword Extraction                                      │
│     ↓                                                       │
│  5. Sentiment Analysis (PhoBERT)                            │
│     ↓                                                       │
│  6. Impact Calculation                                      │
│     ↓                                                       │
│  7. Build AnalyticsResult                                   │
│     ↓                                                       │
│  ┌──────────────────────────────────────────────┐          │
│  │  8a. Database Persistence                    │          │
│  │      → INSERT INTO schema_analysis.post_insight │       │
│  └──────────────────────────────────────────────┘          │
│     ↓                                                       │
│  ┌──────────────────────────────────────────────┐          │
│  │  8b. ResultBuilder                           │          │
│  │      → Transform to Enriched Output          │          │
│  └──────────────────────────────────────────────┘          │
│     ↓                                                       │
│  ┌──────────────────────────────────────────────┐          │
│  │  8c. Kafka Producer                          │          │
│  │      → Publish batch to smap.analytics.output│          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                    ↓                    ↓
         ┌──────────────────┐  ┌──────────────────┐
         │   PostgreSQL     │  │  Kafka Topic     │
         │   post_insight   │  │ analytics.output │
         └──────────────────┘  └──────────────────┘
                                        ↓
                              ┌──────────────────┐
                              │ Knowledge Service│
                              │  (Qdrant Index)  │
                              └──────────────────┘
```

---

## 4. Usage Examples

### 4.1 Query Database

```sql
-- Get all negative posts about VF8
SELECT id, content, overall_sentiment_score, aspects
FROM schema_analysis.post_insight
WHERE project_id = 'proj_vf8_monitor_01'
  AND overall_sentiment = 'NEGATIVE'
  AND content_created_at >= NOW() - INTERVAL '7 days'
ORDER BY engagement_score DESC
LIMIT 10;

-- Find posts with battery complaints
SELECT id, content, aspects
FROM schema_analysis.post_insight
WHERE project_id = 'proj_vf8_monitor_01'
  AND aspects @> '[{"aspect": "BATTERY", "polarity": "NEGATIVE"}]'::jsonb
ORDER BY content_created_at DESC;

-- Get high-risk posts requiring attention
SELECT id, content, risk_level, risk_factors
FROM schema_analysis.post_insight
WHERE requires_attention = true
  AND risk_level IN ('HIGH', 'CRITICAL')
ORDER BY risk_score DESC;
```

### 4.2 Consume Kafka

```python
# Knowledge Service consumer
from aiokafka import AIOKafkaConsumer
import json

consumer = AIOKafkaConsumer(
    'smap.analytics.output',
    bootstrap_servers='172.16.21.206:9092',
    group_id='knowledge-service',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

async for message in consumer:
    batch = message.value  # Array of enriched outputs
    for enriched in batch:
        # Index to Qdrant
        if enriched['rag']['index']['should_index']:
            await index_to_qdrant(enriched)
```

---

## 5. Field Mapping: UAP Input → Database + Kafka

| UAP Input Field             | DB Column                | Kafka Enriched Field          |
| :-------------------------- | :----------------------- | :---------------------------- |
| `event_id`                  | `id` (generated)         | `event_id`                    |
| `ingest.project_id`         | `project_id`             | `project.project_id`          |
| `ingest.source.source_id`   | `source_id`              | `identity.source_id`          |
| `content.text`              | `content`                | `content.text`                |
| `content.published_at`      | `content_created_at`     | `identity.published_at`       |
| `ingest.batch.received_at`  | `ingested_at`            | `identity.ingested_at`        |
| `ingest.source.source_type` | `platform`               | `identity.source_type`        |
| `signals.engagement`        | `uap_metadata.engagement`| `business.impact.engagement`  |
| AI Sentiment Result         | `overall_sentiment`      | `nlp.sentiment`               |
| AI Aspect Result            | `aspects`                | `nlp.aspects`                 |
| AI Keyword Result           | `keywords`               | (embedded in content)         |
| Calculated Engagement Score | `engagement_score`       | `business.impact.engagement_score` |
| Calculated Risk             | `risk_level`, `risk_score` | `business.alerts`           |

---

## 6. Migration Notes

### From Legacy Schema

**Old**: `schema_analyst.analyzed_posts` (flat structure)  
**New**: `schema_analysis.post_insight` (enriched structure)

**Key Changes:**
- Schema name: `schema_analyst` → `schema_analysis`
- Table name: `analyzed_posts` → `post_insight`
- ID type: VARCHAR(255) → UUID
- Added 30+ new columns for enriched analytics
- Added JSONB columns with GIN indexes
- Added Kafka output publishing

**Migration Script**: `migration/003_create_post_insight.sql`

---

## References

- **Database Schema**: `refactor_plan/indexing_input_schema.md`
- **Enriched Output Spec**: `refactor_plan/input-output/output/OUTPUT_EXPLAIN.md`
- **Example Output**: `refactor_plan/input-output/output/output_example.json`
- **Input Format**: `documents/input_payload.md`
- **Master Proposal**: `documents/master-proposal.md`

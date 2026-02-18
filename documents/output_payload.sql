-- ============================================================================
-- SMAP Analysis Service — Output Schema (schema_analysis.post_insight)
-- ============================================================================
-- Table: schema_analysis.post_insight
-- Mô tả cấu trúc dữ liệu output mà pipeline persist vào PostgreSQL.
-- Mỗi record = 1 bài viết đã phân tích đầy đủ (UAP input + kết quả AI enriched).
--
-- Schema này là kết quả của Phase 3 migration, thay thế legacy schema
-- schema_analyst.analyzed_posts với cấu trúc enriched và nhiều fields mới.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS schema_analysis;

CREATE TABLE schema_analysis.post_insight (

    -- ═══════════════════════════════════════════════════════════════════════
    -- CORE IDENTITY
    -- ═══════════════════════════════════════════════════════════════════════

    -- Primary key. UUID định danh duy nhất của record schema_analyst
    -- Generated hoặc từ UAP event_id
    id                      UUID            PRIMARY KEY,

    -- UUID project trên SMAP. Từ UAP ingest.project_id
    -- Dùng để filter trong Campaign (RAG scope)
    project_id              VARCHAR(255)    NOT NULL,

    -- ID của data source. Từ UAP ingest.source.source_id
    -- Truy vết nguồn gốc data
    source_id               VARCHAR(255)    NULL,

    -- ═══════════════════════════════════════════════════════════════════════
    -- CONTENT & TIMESTAMPS
    -- ═══════════════════════════════════════════════════════════════════════

    -- Nội dung text gốc cần phân tích. Từ UAP content.text
    -- Input chính cho AI pipeline và RAG search
    content                 TEXT            NOT NULL,

    -- Thời điểm nội dung được tạo bởi tác giả (Business time)
    -- Từ UAP content.published_at. Dùng cho trend charts, temporal queries
    content_created_at      TIMESTAMPTZ     NOT NULL,

    -- Thời điểm hệ thống nhận dữ liệu (System time)
    -- Từ UAP ingest.batch.received_at. Dùng cho debug, latency measurement
    ingested_at             TIMESTAMPTZ     NOT NULL,

    -- Platform nguồn: facebook, tiktok, youtube, instagram, file_upload, webhook
    -- Từ UAP ingest.source.source_type (lowercase)
    platform                VARCHAR(50)     NOT NULL,

    -- ═══════════════════════════════════════════════════════════════════════
    -- UAP METADATA (JSONB — Schema-less, linh hoạt cho từng platform)
    -- ═══════════════════════════════════════════════════════════════════════

    -- Metadata từ UAP input: author, engagement, url, hashtags, location, etc.
    -- Format: {
    --   "author": "nguyen_van_a_2024",
    --   "author_display_name": "Nguyễn Văn A",
    --   "author_followers": 15000,
    --   "engagement": {"views": 45000, "likes": 3200, "comments": 156, "shares": 89},
    --   "video_url": "https://...",
    --   "hashtags": ["#VinFast", "#VF8"],
    --   "location": "Hà Nội, Việt Nam"
    -- }
    uap_metadata            JSONB           NOT NULL DEFAULT '{}',

    -- ═══════════════════════════════════════════════════════════════════════
    -- SENTIMENT ANALYSIS (PhoBERT ONNX)
    -- ═══════════════════════════════════════════════════════════════════════

    -- Label cảm xúc tổng thể: POSITIVE, NEGATIVE, NEUTRAL, MIXED
    overall_sentiment       VARCHAR(50)     NOT NULL DEFAULT 'NEUTRAL',

    -- Điểm cảm xúc: -1.0 (rất tiêu cực) → 1.0 (rất tích cực)
    overall_sentiment_score FLOAT           NOT NULL DEFAULT 0.0,

    -- Độ tin cậy kết quả sentiment: 0.0 → 1.0
    sentiment_confidence    FLOAT           NOT NULL DEFAULT 0.0,

    -- Giải thích sentiment (future - explainable AI)
    sentiment_explanation   TEXT            NULL,

    -- ═══════════════════════════════════════════════════════════════════════
    -- ASPECT-BASED SENTIMENT (JSONB Array)
    -- ═══════════════════════════════════════════════════════════════════════

    -- Phân tích cảm xúc theo aspect
    -- Format: [
    --   {
    --     "aspect": "BATTERY",
    --     "aspect_display_name": "Pin",
    --     "polarity": "NEGATIVE",
    --     "confidence": 0.74,
    --     "evidence": "pin sụt nhanh",
    --     "mentions": [{"text": "pin sụt nhanh", "start_pos": 15, "end_pos": 29}],
    --     "impact_score": 0.81,
    --     "explanation": "Người dùng phàn nàn về độ bền pin"
    --   }
    -- ]
    aspects                 JSONB           NOT NULL DEFAULT '[]',

    -- ═══════════════════════════════════════════════════════════════════════
    -- KEYWORDS & INTENT
    -- ═══════════════════════════════════════════════════════════════════════

    -- Danh sách từ khóa đã trích xuất (YAKE + spaCy NER)
    keywords                TEXT[]          NOT NULL DEFAULT '{}',

    -- Ý định chính: DISCUSSION, QUESTION, COMPLAINT, PRAISE, SPAM, SEEDING
    primary_intent          VARCHAR(50)     NOT NULL DEFAULT 'DISCUSSION',

    -- Độ tin cậy intent classification: 0.0 → 1.0
    intent_confidence       FLOAT           NOT NULL DEFAULT 0.0,

    -- ═══════════════════════════════════════════════════════════════════════
    -- RISK ASSESSMENT (Multi-factor)
    -- ═══════════════════════════════════════════════════════════════════════

    -- Mức rủi ro: LOW, MEDIUM, HIGH, CRITICAL
    risk_level              VARCHAR(50)     NOT NULL DEFAULT 'LOW',

    -- Điểm risk (0-1) từ multi-factor assessment
    risk_score              FLOAT           NOT NULL DEFAULT 0.0,

    -- Chi tiết risk factors
    -- Format: [
    --   {
    --     "factor": "NEGATIVE_SENTIMENT",
    --     "severity": "MEDIUM",
    --     "description": "Negative sentiment detected (score: -0.45)"
    --   },
    --   {
    --     "factor": "KEYWORD_MATCH",
    --     "severity": "HIGH",
    --     "description": "Crisis keywords detected: lừa đảo, cháy"
    --   }
    -- ]
    risk_factors            JSONB           NOT NULL DEFAULT '[]',

    -- Flag cần xử lý ngay (risk_level = HIGH or CRITICAL)
    requires_attention      BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Flag đã trigger alert
    alert_triggered         BOOLEAN         NOT NULL DEFAULT FALSE,

    -- ═══════════════════════════════════════════════════════════════════════
    -- ENGAGEMENT & IMPACT (Phase 4 - New Calculations)
    -- ═══════════════════════════════════════════════════════════════════════

    -- Điểm engagement (0-100)
    -- Formula: (likes*1 + comments*2 + shares*3) / views * 100, cap 100
    engagement_score        FLOAT           NOT NULL DEFAULT 0.0,

    -- Điểm viral (0+)
    -- Formula: shares / (likes + comments + 1)
    virality_score          FLOAT           NOT NULL DEFAULT 0.0,

    -- Điểm influence (0+)
    -- Formula: (followers / 1M) * engagement_score
    influence_score         FLOAT           NOT NULL DEFAULT 0.0,

    -- Ước tính reach (từ view_count hoặc calculated)
    reach_estimate          INTEGER         NOT NULL DEFAULT 0,

    -- Điểm impact tổng hợp (0-100)
    impact_score            FLOAT           NOT NULL DEFAULT 0.0,

    -- ═══════════════════════════════════════════════════════════════════════
    -- CONTENT QUALITY (Future)
    -- ═══════════════════════════════════════════════════════════════════════

    -- Điểm chất lượng nội dung (future - NLP features)
    content_quality_score   FLOAT           NOT NULL DEFAULT 0.0,

    -- Flag spam detection (Phase 4 - heuristics)
    is_spam                 BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Flag bot detection (future - behavioral analysis)
    is_bot                  BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Ngôn ngữ (future - langdetect)
    language                VARCHAR(10)     NULL,

    -- Độ tin cậy language detection (future)
    language_confidence     FLOAT           NOT NULL DEFAULT 0.0,

    -- Điểm toxic (future - toxicity model)
    toxicity_score          FLOAT           NOT NULL DEFAULT 0.0,

    -- Flag toxic content (future)
    is_toxic                BOOLEAN         NOT NULL DEFAULT FALSE,

    -- ═══════════════════════════════════════════════════════════════════════
    -- PROCESSING METADATA
    -- ═══════════════════════════════════════════════════════════════════════

    -- Thời gian xử lý pipeline (ms)
    processing_time_ms      INTEGER         NOT NULL DEFAULT 0,

    -- Version schema_analyst model/pipeline
    model_version           VARCHAR(50)     NOT NULL DEFAULT '1.0.0',

    -- Trạng thái xử lý: success, error, skipped
    processing_status       VARCHAR(50)     NOT NULL DEFAULT 'success',

    -- Thời điểm phân tích hoàn thành
    analyzed_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Thời điểm index vào vector DB (updated by Knowledge Service)
    indexed_at              TIMESTAMPTZ     NULL,

    -- Thời điểm tạo record
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Thời điểm update record
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════════════════════

-- Primary key
CREATE UNIQUE INDEX idx_post_insight_pkey ON schema_analysis.post_insight(id);

-- Query optimization
CREATE INDEX idx_post_insight_project ON schema_analysis.post_insight(project_id);
CREATE INDEX idx_post_insight_platform ON schema_analysis.post_insight(platform);
CREATE INDEX idx_post_insight_created ON schema_analysis.post_insight(content_created_at DESC);
CREATE INDEX idx_post_insight_analyzed ON schema_analysis.post_insight(analyzed_at DESC);
CREATE INDEX idx_post_insight_sentiment ON schema_analysis.post_insight(overall_sentiment);
CREATE INDEX idx_post_insight_risk ON schema_analysis.post_insight(risk_level);
CREATE INDEX idx_post_insight_intent ON schema_analysis.post_insight(primary_intent);

-- JSONB indexes (GIN for efficient JSONB queries)
CREATE INDEX idx_post_insight_aspects_gin ON schema_analysis.post_insight USING GIN(aspects);
CREATE INDEX idx_post_insight_uap_gin ON schema_analysis.post_insight USING GIN(uap_metadata);
CREATE INDEX idx_post_insight_risk_factors_gin ON schema_analysis.post_insight USING GIN(risk_factors);

-- Composite indexes
CREATE INDEX idx_post_insight_project_created ON schema_analysis.post_insight(project_id, content_created_at DESC);
CREATE INDEX idx_post_insight_project_sentiment ON schema_analysis.post_insight(project_id, overall_sentiment);
CREATE INDEX idx_post_insight_project_risk ON schema_analysis.post_insight(project_id, risk_level);

-- Attention flags
CREATE INDEX idx_post_insight_attention ON schema_analysis.post_insight(requires_attention) WHERE requires_attention = TRUE;
CREATE INDEX idx_post_insight_spam ON schema_analysis.post_insight(is_spam) WHERE is_spam = TRUE;

-- ═══════════════════════════════════════════════════════════════════════════
-- EXAMPLE QUERIES
-- ═══════════════════════════════════════════════════════════════════════════

-- Get all negative posts about a project in last 7 days
-- SELECT id, content, overall_sentiment_score, aspects
-- FROM schema_analysis.post_insight
-- WHERE project_id = 'proj_vf8_monitor_01'
--   AND overall_sentiment = 'NEGATIVE'
--   AND content_created_at >= NOW() - INTERVAL '7 days'
-- ORDER BY engagement_score DESC
-- LIMIT 10;

-- Find posts with specific aspect complaints
-- SELECT id, content, aspects
-- FROM schema_analysis.post_insight
-- WHERE project_id = 'proj_vf8_monitor_01'
--   AND aspects @> '[{"aspect": "BATTERY", "polarity": "NEGATIVE"}]'::jsonb
-- ORDER BY content_created_at DESC;

-- Get high-risk posts requiring attention
-- SELECT id, content, risk_level, risk_factors
-- FROM schema_analysis.post_insight
-- WHERE requires_attention = true
--   AND risk_level IN ('HIGH', 'CRITICAL')
-- ORDER BY risk_score DESC;

-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION NOTES
-- ═══════════════════════════════════════════════════════════════════════════
-- Legacy schema (REMOVED in Phase 6):
-- - Schema: schema_analyst
-- - Table: analyzed_posts
-- - ID type: VARCHAR(255)
-- - Flat structure with limited enrichment
--
-- Current schema (Phase 3+):
-- - Schema: schema_analysis
-- - Table: post_insight
-- - ID type: UUID
-- - Enriched structure with 50+ columns
-- - JSONB columns for flexible metadata
-- - GIN indexes for efficient JSONB queries
-- - Support for Phase 4 business logic (engagement, virality, influence)
-- - Support for Phase 2 Kafka output publishing
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE schema_analysis.post_insight (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    source_id VARCHAR(255),

    -- UAP Core
    content TEXT,
    content_created_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ,
    platform VARCHAR(50),
    uap_metadata JSONB DEFAULT '{}',

    -- Sentiment
    overall_sentiment VARCHAR(20) DEFAULT 'NEUTRAL',
    overall_sentiment_score FLOAT DEFAULT 0.0,
    sentiment_confidence FLOAT DEFAULT 0.0,
    sentiment_explanation TEXT,

    -- ABSA
    aspects JSONB DEFAULT '[]',

    -- Keywords
    keywords TEXT[] DEFAULT '{}',

    -- Risk
    risk_level VARCHAR(20) DEFAULT 'LOW',
    risk_score FLOAT DEFAULT 0.0,
    risk_factors JSONB DEFAULT '[]',
    requires_attention BOOLEAN DEFAULT false,
    alert_triggered BOOLEAN DEFAULT false,

    -- Engagement (calculated)
    engagement_score FLOAT DEFAULT 0.0,
    virality_score FLOAT DEFAULT 0.0,
    influence_score FLOAT DEFAULT 0.0,
    reach_estimate INTEGER DEFAULT 0,

    -- Quality
    content_quality_score FLOAT DEFAULT 0.0,
    is_spam BOOLEAN DEFAULT false,
    is_bot BOOLEAN DEFAULT false,
    language VARCHAR(10),
    language_confidence FLOAT DEFAULT 0.0,
    toxicity_score FLOAT DEFAULT 0.0,
    is_toxic BOOLEAN DEFAULT false,

    -- Processing
    primary_intent VARCHAR(50) DEFAULT 'DISCUSSION',
    intent_confidence FLOAT DEFAULT 0.0,
    impact_score FLOAT DEFAULT 0.0,
    processing_time_ms INTEGER DEFAULT 0,
    model_version VARCHAR(50) DEFAULT '1.0.0',
    processing_status VARCHAR(50) DEFAULT 'success',

    -- Timestamps
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_post_insight_project ON schema_analysis.post_insight(project_id);
CREATE INDEX idx_post_insight_source ON schema_analysis.post_insight(source_id);
CREATE INDEX idx_post_insight_created ON schema_analysis.post_insight(content_created_at);
CREATE INDEX idx_post_insight_sentiment ON schema_analysis.post_insight(overall_sentiment);
CREATE INDEX idx_post_insight_risk ON schema_analysis.post_insight(risk_level);
CREATE INDEX idx_post_insight_platform ON schema_analysis.post_insight(platform);
CREATE INDEX idx_post_insight_analyzed ON schema_analysis.post_insight(analyzed_at);

-- GIN indexes for JSONB
CREATE INDEX idx_post_insight_aspects ON schema_analysis.post_insight USING GIN (aspects);
CREATE INDEX idx_post_insight_uap_metadata ON schema_analysis.post_insight USING GIN (uap_metadata);

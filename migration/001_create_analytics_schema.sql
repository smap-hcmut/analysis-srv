-- Migration: Create schema_analyst schema and post_schema_analyst table
-- Ref: refactor_plan/indexing_input_schema.md

-- 2. Create table
CREATE TABLE schema_analyst.post_schema_analyst (
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

-- 3. Indexes
CREATE INDEX idx_post_schema_analyst_project ON schema_analyst.post_schema_analyst(project_id);
CREATE INDEX idx_post_schema_analyst_source ON schema_analyst.post_schema_analyst(source_id);
CREATE INDEX idx_post_schema_analyst_created ON schema_analyst.post_schema_analyst(content_created_at);
CREATE INDEX idx_post_schema_analyst_sentiment ON schema_analyst.post_schema_analyst(overall_sentiment);
CREATE INDEX idx_post_schema_analyst_risk ON schema_analyst.post_schema_analyst(risk_level);
CREATE INDEX idx_post_schema_analyst_platform ON schema_analyst.post_schema_analyst(platform);
CREATE INDEX idx_post_schema_analyst_attention ON schema_analyst.post_schema_analyst(requires_attention)
    WHERE requires_attention = true;
CREATE INDEX idx_post_schema_analyst_analyzed ON schema_analyst.post_schema_analyst(analyzed_at);

-- Unique Constraint (Business Key)
-- Ensures one schema_analyst record per source post within a project
-- NULL source_id allowed for legacy/error records
CREATE UNIQUE INDEX idx_post_schema_analyst_unique_source ON schema_analyst.post_schema_analyst(project_id, source_id)
    WHERE source_id IS NOT NULL;

-- GIN indexes for JSONB
CREATE INDEX idx_post_schema_analyst_aspects ON schema_analyst.post_schema_analyst USING GIN (aspects);
CREATE INDEX idx_post_schema_analyst_metadata ON schema_analyst.post_schema_analyst USING GIN (uap_metadata);

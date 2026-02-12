-- Migration: Create analyzed_posts table
-- Description: Table to store analyzed social media posts with sentiment, intent, and impact data
-- Author: Analytics Team
-- Date: 2024-02-12

-- Create analyzed_posts table
CREATE TABLE IF NOT EXISTS schema_analyst.analyzed_posts (
    -- Primary key
    id VARCHAR(255) PRIMARY KEY,
    
    -- Identifiers
    project_id VARCHAR(255),
    platform VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    
    -- Timestamps
    published_at TIMESTAMPTZ,
    analyzed_at TIMESTAMPTZ,
    
    -- Sentiment
    overall_sentiment VARCHAR(50) NOT NULL DEFAULT 'NEUTRAL',
    overall_sentiment_score FLOAT NOT NULL DEFAULT 0.0,
    overall_confidence FLOAT NOT NULL DEFAULT 0.0,
    
    -- Intent
    primary_intent VARCHAR(50) NOT NULL DEFAULT 'DISCUSSION',
    intent_confidence FLOAT NOT NULL DEFAULT 0.0,
    
    -- Impact
    impact_score FLOAT NOT NULL DEFAULT 0.0,
    risk_level VARCHAR(50) NOT NULL DEFAULT 'LOW',
    is_viral BOOLEAN NOT NULL DEFAULT FALSE,
    is_kol BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Breakdowns (JSONB for PostgreSQL)
    aspects_breakdown JSONB NOT NULL DEFAULT '{}',
    keywords TEXT[] NOT NULL DEFAULT '{}',
    sentiment_probabilities JSONB NOT NULL DEFAULT '{}',
    impact_breakdown JSONB NOT NULL DEFAULT '{}',
    
    -- Raw metrics
    view_count INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    share_count INTEGER NOT NULL DEFAULT 0,
    save_count INTEGER NOT NULL DEFAULT 0,
    follower_count INTEGER NOT NULL DEFAULT 0,
    
    -- Processing metadata
    processing_time_ms INTEGER NOT NULL DEFAULT 0,
    model_version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    processing_status VARCHAR(50) NOT NULL DEFAULT 'success',
    
    -- Crawler metadata (Contract v2.0)
    job_id VARCHAR(255),
    batch_index INTEGER,
    task_type VARCHAR(50),
    keyword_source VARCHAR(255),
    crawled_at TIMESTAMPTZ,
    pipeline_version VARCHAR(50),
    brand_name VARCHAR(255),
    keyword VARCHAR(255),
    
    -- Content fields
    content_text TEXT,
    content_transcription TEXT,
    media_duration INTEGER,
    hashtags TEXT[],
    permalink TEXT,
    
    -- Author fields
    author_id VARCHAR(255),
    author_name VARCHAR(255),
    author_username VARCHAR(255),
    author_avatar_url TEXT,
    author_is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_analyzed_posts_project_id 
    ON schema_analyst.analyzed_posts(project_id);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_job_id 
    ON schema_analyst.analyzed_posts(job_id);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_analyzed_at 
    ON schema_analyst.analyzed_posts(analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_platform 
    ON schema_analyst.analyzed_posts(platform);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_risk_level 
    ON schema_analyst.analyzed_posts(risk_level);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_is_viral 
    ON schema_analyst.analyzed_posts(is_viral) 
    WHERE is_viral = TRUE;

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_is_kol 
    ON schema_analyst.analyzed_posts(is_kol) 
    WHERE is_kol = TRUE;

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_sentiment 
    ON schema_analyst.analyzed_posts(overall_sentiment);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_intent 
    ON schema_analyst.analyzed_posts(primary_intent);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_analyzed_posts_project_analyzed 
    ON schema_analyst.analyzed_posts(project_id, analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_analyzed_posts_job_batch 
    ON schema_analyst.analyzed_posts(job_id, batch_index);

-- Add comment to table
COMMENT ON TABLE schema_analyst.analyzed_posts IS 
    'Stores analyzed social media posts with sentiment, intent, and impact analysis results';

-- Add comments to important columns
COMMENT ON COLUMN schema_analyst.analyzed_posts.id IS 
    'Unique identifier for the post (from source platform)';

COMMENT ON COLUMN schema_analyst.analyzed_posts.project_id IS 
    'UUID of the project this post belongs to';

COMMENT ON COLUMN schema_analyst.analyzed_posts.overall_sentiment IS 
    'Overall sentiment: POSITIVE, NEGATIVE, or NEUTRAL';

COMMENT ON COLUMN schema_analyst.analyzed_posts.primary_intent IS 
    'Primary intent: DISCUSSION, QUESTION, COMPLAINT, PRAISE, SPAM, or SEEDING';

COMMENT ON COLUMN schema_analyst.analyzed_posts.impact_score IS 
    'Normalized impact score (0-100) based on engagement and reach';

COMMENT ON COLUMN schema_analyst.analyzed_posts.risk_level IS 
    'Risk level: LOW, MEDIUM, HIGH, or CRITICAL';

COMMENT ON COLUMN schema_analyst.analyzed_posts.aspects_breakdown IS 
    'JSONB containing aspect-level sentiment analysis';

COMMENT ON COLUMN schema_analyst.analyzed_posts.keywords IS 
    'Array of extracted keywords from the post';

COMMENT ON COLUMN schema_analyst.analyzed_posts.processing_status IS 
    'Processing status: success, error, or skipped';

-- Grant permissions (adjust as needed for your environment)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON schema_analyst.analyzed_posts TO analyst_prod;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA schema_analyst TO analyst_prod;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Migration 001_create_analyzed_posts_table.sql completed successfully';
END $$;

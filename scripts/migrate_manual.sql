-- Manual migration script for Analytics Engine
-- Run this script against your PostgreSQL database

-- Create post_analytics table
CREATE TABLE IF NOT EXISTS post_analytics (
    id VARCHAR(50) PRIMARY KEY,
    project_id UUID,
    platform VARCHAR(20) NOT NULL,
    
    -- Timestamps
    published_at TIMESTAMP NOT NULL,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    
    -- Overall analysis
    overall_sentiment VARCHAR(10) NOT NULL,
    overall_sentiment_score FLOAT,
    overall_confidence FLOAT,
    
    -- Intent
    primary_intent VARCHAR(20) NOT NULL,
    intent_confidence FLOAT,
    
    -- Impact
    impact_score FLOAT NOT NULL,
    risk_level VARCHAR(10) NOT NULL,
    is_viral BOOLEAN DEFAULT FALSE,
    is_kol BOOLEAN DEFAULT FALSE,
    
    -- JSONB columns
    aspects_breakdown JSONB,
    keywords JSONB,
    sentiment_probabilities JSONB,
    impact_breakdown JSONB,
    
    -- Raw metrics
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    save_count INTEGER DEFAULT 0,
    follower_count INTEGER DEFAULT 0,
    
    -- Processing metadata
    processing_time_ms INTEGER,
    model_version VARCHAR(50),
    
    -- Batch context
    job_id VARCHAR(100),
    batch_index INTEGER,
    task_type VARCHAR(30),
    
    -- Crawler metadata
    keyword_source VARCHAR(200),
    crawled_at TIMESTAMP,
    pipeline_version VARCHAR(50),
    
    -- Error tracking
    fetch_status VARCHAR(10) DEFAULT 'success',
    fetch_error TEXT,
    error_code VARCHAR(50),
    error_details JSONB
);

-- Create indexes for post_analytics
CREATE INDEX IF NOT EXISTS idx_post_analytics_job_id ON post_analytics(job_id);
CREATE INDEX IF NOT EXISTS idx_post_analytics_fetch_status ON post_analytics(fetch_status);
CREATE INDEX IF NOT EXISTS idx_post_analytics_task_type ON post_analytics(task_type);
CREATE INDEX IF NOT EXISTS idx_post_analytics_error_code ON post_analytics(error_code);

-- Create crawl_errors table
CREATE TABLE IF NOT EXISTS crawl_errors (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(50) NOT NULL,
    project_id UUID,
    job_id VARCHAR(100) NOT NULL,
    platform VARCHAR(20) NOT NULL,
    
    -- Error details
    error_code VARCHAR(50) NOT NULL,
    error_category VARCHAR(30) NOT NULL,
    error_message TEXT,
    error_details JSONB,
    
    -- Content reference
    permalink TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for crawl_errors
CREATE INDEX IF NOT EXISTS idx_crawl_errors_project_id ON crawl_errors(project_id);
CREATE INDEX IF NOT EXISTS idx_crawl_errors_error_code ON crawl_errors(error_code);
CREATE INDEX IF NOT EXISTS idx_crawl_errors_created_at ON crawl_errors(created_at);
CREATE INDEX IF NOT EXISTS idx_crawl_errors_job_id ON crawl_errors(job_id);

-- If table already exists, add missing columns (safe to run multiple times)
DO $$
BEGIN
    -- Add columns to post_analytics if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='job_id') THEN
        ALTER TABLE post_analytics ADD COLUMN job_id VARCHAR(100);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='batch_index') THEN
        ALTER TABLE post_analytics ADD COLUMN batch_index INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='task_type') THEN
        ALTER TABLE post_analytics ADD COLUMN task_type VARCHAR(30);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='keyword_source') THEN
        ALTER TABLE post_analytics ADD COLUMN keyword_source VARCHAR(200);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='crawled_at') THEN
        ALTER TABLE post_analytics ADD COLUMN crawled_at TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='pipeline_version') THEN
        ALTER TABLE post_analytics ADD COLUMN pipeline_version VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='fetch_status') THEN
        ALTER TABLE post_analytics ADD COLUMN fetch_status VARCHAR(10) DEFAULT 'success';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='fetch_error') THEN
        ALTER TABLE post_analytics ADD COLUMN fetch_error TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='error_code') THEN
        ALTER TABLE post_analytics ADD COLUMN error_code VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='post_analytics' AND column_name='error_details') THEN
        ALTER TABLE post_analytics ADD COLUMN error_details JSONB;
    END IF;
END $$;

-- Verify tables
SELECT 'post_analytics columns:' as info;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'post_analytics' ORDER BY ordinal_position;

SELECT 'crawl_errors columns:' as info;
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'crawl_errors' ORDER BY ordinal_position;

-- 002_create_analytics_run_manifest.sql
-- Run manifest table for audit/replay (Phase 6).

CREATE TABLE IF NOT EXISTS analysis.analytics_run_manifest (
    run_id      TEXT        PRIMARY KEY,
    project_id  TEXT        NOT NULL,
    campaign_id TEXT        NOT NULL,
    data        JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_run_manifest_project
    ON analysis.analytics_run_manifest (project_id, campaign_id);

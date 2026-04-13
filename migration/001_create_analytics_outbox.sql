-- 001_create_analytics_outbox.sql
-- Transactional outbox table for reliable Kafka delivery (Phase 6).

CREATE TABLE IF NOT EXISTS schema_analysis.analytics_outbox (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      TEXT        NOT NULL,
    topic       TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed')),
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at     TIMESTAMPTZ
);

-- Fast poll of pending records ordered by insertion time
CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON schema_analysis.analytics_outbox (status, created_at)
    WHERE status = 'pending';

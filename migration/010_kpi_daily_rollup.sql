-- Per-day KPI rollup table populated from the deduped latest_post_insight
-- mart. Lets analytics_kpis answer the Insight dashboard from O(365) rows per
-- project instead of aggregating O(500k) raw rows on every request.
--
-- The rollup is refreshed alongside latest_post_insight (function chain in
-- refresh_latest_post_insight) so consumers and the hourly mart job both
-- keep it up to date. No new cron is added.

CREATE TABLE IF NOT EXISTS analysis.kpi_daily (
  project_id     TEXT             NOT NULL,
  bucket_date    DATE             NOT NULL,
  mentions       BIGINT           NOT NULL DEFAULT 0,
  sentiment_sum  DOUBLE PRECISION NOT NULL DEFAULT 0,
  engagement_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
  reach_sum      DOUBLE PRECISION NOT NULL DEFAULT 0,
  views_sum      BIGINT           NOT NULL DEFAULT 0,
  likes_sum      BIGINT           NOT NULL DEFAULT 0,
  comments_sum  BIGINT            NOT NULL DEFAULT 0,
  shares_sum    BIGINT            NOT NULL DEFAULT 0,
  refreshed_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, bucket_date)
);

CREATE INDEX IF NOT EXISTS idx_kpi_daily_project_date_desc
  ON analysis.kpi_daily (project_id, bucket_date DESC);

GRANT SELECT ON analysis.kpi_daily TO analysis_prod;

-- refresh_kpi_daily collapses the deduped mart into per-day buckets. Runs as
-- INSERT ... ON CONFLICT DO UPDATE so it is idempotent — replaying the
-- function after an incremental ingest keeps the totals exact, not doubled.
CREATE OR REPLACE FUNCTION analysis.refresh_kpi_daily()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  lock_acquired BOOLEAN;
BEGIN
  SELECT pg_try_advisory_xact_lock(hashtext('analysis.refresh_kpi_daily')) INTO lock_acquired;
  IF NOT lock_acquired THEN
    RAISE NOTICE 'refresh_kpi_daily: another refresh is in progress; skipping';
    RETURN;
  END IF;

  -- Truncate-then-rebuild keeps the table consistent with the mart even when
  -- old rows are removed by hide-target or business-relevance flips. Cheap
  -- because kpi_daily is tiny relative to post_insight (one row per project
  -- per day).
  TRUNCATE TABLE analysis.kpi_daily;

  INSERT INTO analysis.kpi_daily (
    project_id, bucket_date, mentions, sentiment_sum, engagement_sum,
    reach_sum, views_sum, likes_sum, comments_sum, shares_sum, refreshed_at
  )
  SELECT
    project_id,
    DATE_TRUNC('day', content_created_at)::DATE AS bucket_date,
    COUNT(*) AS mentions,
    SUM(COALESCE(overall_sentiment_score, 0)) AS sentiment_sum,
    SUM(COALESCE(engagement_score, 0)) AS engagement_sum,
    SUM(COALESCE(reach_estimate, 0)) AS reach_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'views')::BIGINT, 0)) AS views_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'likes')::BIGINT, 0)) AS likes_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'comments')::BIGINT, 0)) AS comments_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'shares')::BIGINT, 0)) AS shares_sum,
    NOW()
  FROM analysis.latest_post_insight
  WHERE content_created_at IS NOT NULL
    AND project_id IS NOT NULL
  GROUP BY project_id, DATE_TRUNC('day', content_created_at)::DATE;
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_kpi_daily() TO analysis_prod;

-- Chain kpi_daily refresh after the mart refresh so a single SELECT call
-- keeps both rollups synchronized. Overwrites the function from migration 007
-- / 008; safe because CREATE OR REPLACE keeps grants intact.
CREATE OR REPLACE FUNCTION analysis.refresh_latest_post_insight()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
  PERFORM analysis.refresh_kpi_daily();
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_latest_post_insight() TO analysis_prod;

-- One-shot backfill so the rollup is populated immediately after the
-- migration runs; the chained refresh above keeps it up to date.
SELECT analysis.refresh_kpi_daily();

ANALYZE analysis.kpi_daily;

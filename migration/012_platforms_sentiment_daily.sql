-- Per-(project_id, platform, sentiment, bucket_date) rollup so the Insight
-- platforms + sentiment tabs answer from a tiny aggregate instead of
-- scanning latest_post_insight on every request. Same chain pattern as
-- kpi_daily: refresh is hooked into refresh_latest_post_insight.

CREATE TABLE IF NOT EXISTS analysis.metrics_daily (
  project_id        TEXT             NOT NULL,
  bucket_date       DATE             NOT NULL,
  platform          TEXT             NOT NULL DEFAULT 'UNKNOWN',
  sentiment         TEXT             NOT NULL DEFAULT 'UNKNOWN',
  mentions          BIGINT           NOT NULL DEFAULT 0,
  sentiment_score   DOUBLE PRECISION NOT NULL DEFAULT 0,
  engagement_sum    DOUBLE PRECISION NOT NULL DEFAULT 0,
  reach_sum         DOUBLE PRECISION NOT NULL DEFAULT 0,
  refreshed_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, bucket_date, platform, sentiment)
);

CREATE INDEX IF NOT EXISTS idx_metrics_daily_project_date
  ON analysis.metrics_daily (project_id, bucket_date DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_daily_project_platform
  ON analysis.metrics_daily (project_id, platform, bucket_date DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_daily_project_sentiment
  ON analysis.metrics_daily (project_id, sentiment, bucket_date DESC);

GRANT SELECT ON analysis.metrics_daily TO analysis_prod;

CREATE OR REPLACE FUNCTION analysis.refresh_metrics_daily()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  acquired BOOLEAN;
BEGIN
  SELECT pg_try_advisory_xact_lock(hashtext('analysis.refresh_metrics_daily'))
    INTO acquired;
  IF NOT acquired THEN
    RAISE NOTICE 'refresh_metrics_daily: skipping concurrent refresh';
    RETURN;
  END IF;

  TRUNCATE TABLE analysis.metrics_daily;

  INSERT INTO analysis.metrics_daily (
    project_id, bucket_date, platform, sentiment,
    mentions, sentiment_score, engagement_sum, reach_sum, refreshed_at
  )
  SELECT
    project_id,
    DATE_TRUNC('day', content_created_at)::DATE AS bucket_date,
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
    COALESCE(NULLIF(UPPER(overall_sentiment), ''), 'UNKNOWN') AS sentiment,
    COUNT(*)                                          AS mentions,
    AVG(COALESCE(overall_sentiment_score, 0))         AS sentiment_score,
    SUM(COALESCE(engagement_score, 0))                AS engagement_sum,
    SUM(COALESCE(reach_estimate, 0))                  AS reach_sum,
    NOW()
  FROM analysis.latest_post_insight
  WHERE content_created_at IS NOT NULL
    AND project_id IS NOT NULL
  GROUP BY
    project_id,
    DATE_TRUNC('day', content_created_at)::DATE,
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
    COALESCE(NULLIF(UPPER(overall_sentiment), ''), 'UNKNOWN');
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_metrics_daily() TO analysis_prod;

CREATE OR REPLACE FUNCTION analysis.refresh_latest_post_insight()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
  PERFORM analysis.refresh_kpi_daily();
  PERFORM analysis.refresh_posts_recent_top();
  PERFORM analysis.refresh_metrics_daily();
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_latest_post_insight() TO analysis_prod;

SELECT analysis.refresh_metrics_daily();
ANALYZE analysis.metrics_daily;

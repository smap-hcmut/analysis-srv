-- Top-N posts rollup per project for the Insight feed (latest + engagement
-- sort). Without this the API was scanning all of latest_post_insight on
-- every /api/analytics/posts call, dominating the 909ms p95 we measured for
-- posts_engagement and 734ms p95 for posts_latest on 2026-06-07.

CREATE TABLE IF NOT EXISTS analysis.posts_recent_top (
  project_id         TEXT             NOT NULL,
  uap_id             TEXT             NOT NULL,
  source_id          TEXT,
  platform           TEXT,
  content_excerpt    TEXT,
  author             TEXT,
  content_created_at TIMESTAMPTZ,
  overall_sentiment  TEXT,
  sentiment_score    DOUBLE PRECISION,
  engagement_score   DOUBLE PRECISION,
  reach_estimate     DOUBLE PRECISION,
  url                TEXT,
  uap_metadata       JSONB,
  refreshed_at       TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
  PRIMARY KEY (project_id, uap_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_recent_top_project_time
  ON analysis.posts_recent_top (project_id, content_created_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_posts_recent_top_project_engagement
  ON analysis.posts_recent_top (project_id, engagement_score DESC NULLS LAST);

GRANT SELECT ON analysis.posts_recent_top TO analysis_prod;

-- refresh_posts_recent_top rebuilds the table with the top 1000 posts per
-- project (newest first), then deduped/refreshed alongside the existing
-- latest_post_insight mat view.
CREATE OR REPLACE FUNCTION analysis.refresh_posts_recent_top()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  acquired BOOLEAN;
BEGIN
  SELECT pg_try_advisory_xact_lock(hashtext('analysis.refresh_posts_recent_top'))
    INTO acquired;
  IF NOT acquired THEN
    RAISE NOTICE 'refresh_posts_recent_top: skipping concurrent refresh';
    RETURN;
  END IF;

  TRUNCATE TABLE analysis.posts_recent_top;

  INSERT INTO analysis.posts_recent_top (
    project_id, uap_id, source_id, platform, content_excerpt, author,
    content_created_at, overall_sentiment, sentiment_score, engagement_score,
    reach_estimate, url, uap_metadata, refreshed_at
  )
  SELECT
    project_id,
    COALESCE(uap_metadata->>'uap_id', source_id) AS uap_id,
    source_id,
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
    LEFT(content, 320)                                AS content_excerpt,
    COALESCE(
      uap_metadata->>'author_display_name',
      uap_metadata->>'author_username',
      uap_metadata->>'author'
    )                                                 AS author,
    content_created_at,
    overall_sentiment,
    overall_sentiment_score                           AS sentiment_score,
    engagement_score,
    reach_estimate,
    COALESCE(
      uap_metadata->>'post_url',
      uap_metadata->>'url',
      uap_metadata->>'permalink_url',
      uap_metadata->>'original_url'
    )                                                 AS url,
    uap_metadata,
    NOW()
  FROM (
    SELECT *,
           ROW_NUMBER() OVER (
             PARTITION BY project_id
             ORDER BY content_created_at DESC NULLS LAST,
                      engagement_score DESC NULLS LAST
           ) AS rn
    FROM analysis.latest_post_insight
    WHERE content_created_at IS NOT NULL
      AND project_id IS NOT NULL
  ) ranked
  WHERE ranked.rn <= 1000;
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_posts_recent_top() TO analysis_prod;

-- Chain into the existing mart refresh so a single call keeps every rollup
-- coherent. Overwrites the function published in migration 010.
CREATE OR REPLACE FUNCTION analysis.refresh_latest_post_insight()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
  PERFORM analysis.refresh_kpi_daily();
  PERFORM analysis.refresh_posts_recent_top();
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_latest_post_insight() TO analysis_prod;

SELECT analysis.refresh_posts_recent_top();
ANALYZE analysis.posts_recent_top;

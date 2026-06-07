-- Rebuild latest_post_insight using WITH NO DATA so the migration finishes
-- instantly. The first incremental REFRESH is left for the background loop
-- in analysis-api (which is now cancel-safe per main.py changes).
--
-- Filter is now domain-agnostic — relevance >= 0.30 OR focused_page/profile.
-- Filtering by domain vocabulary moves to the consumer where it can read the
-- project's ontology rules.

DROP MATERIALIZED VIEW IF EXISTS analysis.latest_post_insight CASCADE;

CREATE MATERIALIZED VIEW analysis.latest_post_insight AS
SELECT DISTINCT ON (
  COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
  COALESCE(
    NULLIF(pi.source_id, ''),
    NULLIF(pi.uap_metadata->>'post_id', ''),
    NULLIF(pi.uap_metadata->>'comment_id', ''),
    NULLIF(pi.uap_metadata->>'video_id', ''),
    NULLIF(pi.uap_metadata->>'url', ''),
    pi.id::text
  )
)
  pi.*
FROM analysis.post_insight pi
WHERE
  COALESCE(pi.business_relevance_score, 0) >= 0.30
  OR COALESCE(pi.uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
ORDER BY
  COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
  COALESCE(
    NULLIF(pi.source_id, ''),
    NULLIF(pi.uap_metadata->>'post_id', ''),
    NULLIF(pi.uap_metadata->>'comment_id', ''),
    NULLIF(pi.uap_metadata->>'video_id', ''),
    NULLIF(pi.uap_metadata->>'url', ''),
    pi.id::text
  ),
  COALESCE(pi.updated_at, pi.analyzed_at, pi.ingested_at, pi.created_at) DESC NULLS LAST,
  pi.created_at DESC NULLS LAST,
  pi.id DESC
WITH NO DATA;

-- Unique index required so refresh_latest_post_insight can use CONCURRENTLY.
CREATE UNIQUE INDEX idx_latest_post_insight_id
  ON analysis.latest_post_insight (id);

CREATE INDEX idx_latest_post_insight_project_relevance
  ON analysis.latest_post_insight (project_id, business_relevance_score);

CREATE INDEX idx_latest_post_insight_project_engagement
  ON analysis.latest_post_insight (
    project_id,
    engagement_score DESC NULLS LAST,
    content_created_at DESC NULLS LAST
  );

CREATE INDEX idx_latest_post_insight_project_time
  ON analysis.latest_post_insight (project_id, content_created_at DESC NULLS LAST);

CREATE INDEX idx_latest_post_insight_project_platform_sentiment
  ON analysis.latest_post_insight (
    project_id,
    (COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN')),
    (UPPER(COALESCE(overall_sentiment, '')))
  );

CREATE INDEX idx_latest_post_insight_project_source_kind
  ON analysis.latest_post_insight (
    project_id,
    (COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', ''))
  );

CREATE INDEX idx_latest_post_insight_keywords
  ON analysis.latest_post_insight USING GIN (keywords);

CREATE INDEX idx_latest_post_insight_engagement_views
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'views')::bigint) DESC NULLS LAST
  );

CREATE INDEX idx_latest_post_insight_engagement_likes
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'likes')::bigint) DESC NULLS LAST
  );

CREATE INDEX idx_latest_post_insight_engagement_comments
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'comments')::bigint) DESC NULLS LAST
  );

CREATE INDEX idx_latest_post_insight_engagement_shares
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'shares')::bigint) DESC NULLS LAST
  );

CREATE INDEX idx_latest_post_insight_kpi_sparkline
  ON analysis.latest_post_insight (
    project_id,
    content_created_at DESC NULLS LAST
  )
  INCLUDE (overall_sentiment_score, engagement_score, reach_estimate);

GRANT SELECT ON analysis.latest_post_insight TO analysis_prod;

-- Refresh chain — CONCURRENTLY so analysis-api refresh loop never holds
-- AccessExclusiveLock that could starve readers (the root cause of the
-- monitor.tantai.dev outage when refresh stacked across pod restarts).
CREATE OR REPLACE FUNCTION analysis.refresh_latest_post_insight()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  acquired BOOLEAN;
  existing_count INTEGER;
BEGIN
  -- Bail out early if another backend is already running the same refresh.
  -- pg_advisory_xact_lock alone is not enough because a client-cancelled
  -- session releases the lock while the CREATE / REFRESH backend keeps
  -- chewing CPU on the planner.
  SELECT count(*) INTO existing_count
    FROM pg_stat_activity
   WHERE state = 'active'
     AND pid <> pg_backend_pid()
     AND query ILIKE '%REFRESH MATERIALIZED VIEW%latest_post_insight%';
  IF existing_count > 0 THEN
    RAISE NOTICE 'refresh_latest_post_insight: another refresh is in progress; skipping';
    RETURN;
  END IF;

  SELECT pg_try_advisory_xact_lock(hashtext('analysis.refresh_latest_post_insight'))
    INTO acquired;
  IF NOT acquired THEN
    RAISE NOTICE 'refresh_latest_post_insight: advisory lock held; skipping';
    RETURN;
  END IF;

  REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
  PERFORM analysis.refresh_kpi_daily();
  PERFORM analysis.refresh_posts_recent_top();
  PERFORM analysis.refresh_metrics_daily();
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_latest_post_insight() TO analysis_prod;

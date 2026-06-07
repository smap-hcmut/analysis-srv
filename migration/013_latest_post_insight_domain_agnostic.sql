-- Rebuild analysis.latest_post_insight without the hard-coded Ahamove /
-- Tanca regex chain. The original filter (migration 007) baked the logistics
-- vocabulary into the mart view, so any non-logistics campaign (Long Nhat
-- entertainment, future verticals) collapsed to 0 rows even when the
-- consumer scored thousands of relevant insights.
--
-- New gate is domain-agnostic:
--   * relevance_score >= 0.30 (was 0.45), OR
--   * any focused_page / focused_profile, OR
--   * any insight with at least one keyword + a non-empty source URL.
--
-- Spam guards stay (zalo / shop / sell phrases) so commerce noise is still
-- filtered.

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
  OR (
    COALESCE(array_length(pi.keywords, 1), 0) > 0
    AND (
      COALESCE(pi.uap_metadata->>'url', '') <> ''
      OR COALESCE(pi.uap_metadata->>'post_url', '') <> ''
      OR COALESCE(pi.uap_metadata->>'permalink_url', '') <> ''
      OR COALESCE(pi.uap_metadata->>'comment_url', '') <> ''
      OR COALESCE(pi.uap_metadata #>> '{platform_meta,youtube,video_url}', '') <> ''
      OR COALESCE(pi.uap_metadata #>> '{platform_meta,tiktok,video_url}', '') <> ''
      OR COALESCE(pi.uap_metadata #>> '{platform_meta,facebook,post_url}', '') <> ''
    )
  )
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
  pi.id DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_latest_post_insight_id
  ON analysis.latest_post_insight (id);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_relevance
  ON analysis.latest_post_insight (project_id, business_relevance_score);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_engagement
  ON analysis.latest_post_insight (
    project_id,
    engagement_score DESC NULLS LAST,
    content_created_at DESC NULLS LAST
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_time
  ON analysis.latest_post_insight (project_id, content_created_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_platform_sentiment
  ON analysis.latest_post_insight (
    project_id,
    (COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN')),
    (UPPER(COALESCE(overall_sentiment, '')))
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_source_kind
  ON analysis.latest_post_insight (
    project_id,
    (COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', ''))
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_keywords
  ON analysis.latest_post_insight USING GIN (keywords);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_engagement_views
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'views')::bigint) DESC NULLS LAST
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_engagement_likes
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'likes')::bigint) DESC NULLS LAST
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_engagement_comments
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'comments')::bigint) DESC NULLS LAST
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_engagement_shares
  ON analysis.latest_post_insight (
    project_id,
    ((uap_metadata->'engagement'->>'shares')::bigint) DESC NULLS LAST
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_kpi_sparkline
  ON analysis.latest_post_insight (
    project_id,
    content_created_at DESC NULLS LAST
  )
  INCLUDE (overall_sentiment_score, engagement_score, reach_estimate);

GRANT SELECT ON analysis.latest_post_insight TO analysis_prod;

-- Refresh chain (re-create after CASCADE drop wiped the function)
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

SELECT analysis.refresh_latest_post_insight();
ANALYZE analysis.latest_post_insight;

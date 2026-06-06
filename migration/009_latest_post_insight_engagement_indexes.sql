-- Expression indexes on the JSON engagement paths used by the Insight KPI
-- query. Without these, every (uap_metadata->'engagement'->>'views')::bigint
-- access during SUM aggregates falls through to a heap fetch + JSON parse,
-- which dominated p95 = 1525 ms on analytics_kpis in the 2026-05-20 bench.
--
-- These do not replace the planned kpi_daily rollup table (SMAP_PERF_DEBUG
-- ISSUE-02 fix #3) but cut the per-row JSON cost for the existing
-- on-the-fly aggregate path until the rollup ships.

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

-- Covering index for the 12-month KPI sparkline query
-- (project_id + content_created_at + sentiment + engagement_score). Lets
-- Postgres satisfy the GROUP BY (month) plan without touching the heap.
CREATE INDEX IF NOT EXISTS idx_latest_post_insight_kpi_sparkline
  ON analysis.latest_post_insight (
    project_id,
    content_created_at DESC NULLS LAST
  )
  INCLUDE (overall_sentiment_score, engagement_score, reach_estimate);

ANALYZE analysis.latest_post_insight;

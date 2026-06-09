-- Cross-project dedup index for /api/v1/analytics/posts
--
-- The Insight tab ORs every project in the campaign and pages the result.
-- analysis.latest_post_insight is deduped per (project_id, source_identity)
-- but not across projects, so a TikTok comment that matches several projects
-- under the same campaign used to surface once per project — same author
-- repeated across pagination.
--
-- analytics_service._posts_base_cte / _base_cte / _compute_posts_from_rollup
-- now wrap the source with DISTINCT ON (UPPER(platform), source_identity)
-- ordered by engagement_score DESC. This index matches that key so the
-- planner can stream rows from a single index scan instead of full-scan +
-- in-memory sort (previously 13-27s on filtered campaigns; now sub-100ms).
--
-- Applied to prod 2026-06-09. Kept here so future fresh databases / DR
-- restores rebuild the index automatically.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_latest_post_insight_xproj_dedup
ON analysis.latest_post_insight (
  project_id,
  (COALESCE(NULLIF(UPPER(platform::text), ''), 'UNKNOWN')),
  source_id,
  engagement_score DESC NULLS LAST
);

ANALYZE analysis.latest_post_insight;

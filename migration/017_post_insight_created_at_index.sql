-- Cover auto_ontology's _fetch_candidates query
-- (analysis-consumer, 3 pods, every 30 min, last 6h window).
-- Without this index the query falls back to a parallel seq scan over
-- all of analysis.post_insight and steals IO from the per-project rollup
-- refresh loop. Existing idx_post_insight_created is on
-- content_created_at, not created_at, so the planner cannot use it.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_post_insight_created_at
  ON analysis.post_insight (created_at DESC);

ANALYZE analysis.post_insight;

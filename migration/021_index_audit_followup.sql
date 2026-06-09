-- Index audit follow-up to 020 (2026-06-09).
--
-- 020 added idx_latest_post_insight_xproj_dedup with an explicit ::text cast
-- on platform. The codegen in analytics_service.AnalyticsService writes the
-- expression without the cast (`UPPER(pi.platform)` against character varying),
-- so PostgreSQL refused to match the index and the slow path still seq-scanned
-- the mart (5–18 s under load). Drop the old definition and recreate the
-- expression to match codegen byte-for-byte. Also add a content_type CASE
-- index so the filtered Insight queries (post/comment/reply) stop reverting
-- to in-memory CASE evaluation over the full project slice.
--
-- Index housekeeping: three indexes on analysis.post_insight had zero scans
-- cluster-wide and were costing 628 MB of disk + a WAL write on every upsert.
-- Drop them — the table sees ~56 k upserts/min, so write-amplification matters
-- more than keeping safety nets around. Re-add if a future workload needs them.

DROP INDEX CONCURRENTLY IF EXISTS analysis.idx_latest_post_insight_xproj_dedup;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_latest_post_insight_xproj_dedup
ON analysis.latest_post_insight (
  project_id,
  (COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN')),
  source_id,
  engagement_score DESC NULLS LAST
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_latest_post_insight_project_ctype
ON analysis.latest_post_insight (
  project_id,
  (
    CASE
      WHEN COALESCE(uap_metadata #>> '{hierarchy,depth}', '') ~ '^[2-9]'
        OR LOWER(COALESCE(uap_metadata->>'doc_type', uap_metadata->>'uap_type', '')) = 'reply' THEN 'reply'
      WHEN COALESCE(uap_metadata #>> '{hierarchy,depth}', '') = '1'
        OR LOWER(COALESCE(uap_metadata->>'doc_type', uap_metadata->>'uap_type', '')) = 'comment'
        OR (UPPER(COALESCE(platform, '')) = 'YOUTUBE' AND (COALESCE(uap_metadata->>'url', '') LIKE '%&lc=%' OR COALESCE(uap_metadata->>'url', '') LIKE '%?lc=%' OR COALESCE(source_id, '') LIKE 'Ug%')) THEN 'comment'
      WHEN COALESCE(uap_metadata #>> '{hierarchy,depth}', '') = '0'
        OR LOWER(COALESCE(uap_metadata->>'doc_type', uap_metadata->>'uap_type', '')) IN ('post','video','news','feedback') THEN 'post'
      ELSE 'mention'
    END
  )
);

DROP INDEX CONCURRENTLY IF EXISTS analysis.idx_post_insight_project_url_updated;
DROP INDEX CONCURRENTLY IF EXISTS analysis.idx_post_insight_aspects;
DROP INDEX CONCURRENTLY IF EXISTS analysis.idx_post_insight_risk;

ANALYZE analysis.post_insight;
ANALYZE analysis.latest_post_insight;
ANALYZE analysis.posts_recent_top;
ANALYZE analysis.kpi_daily;
ANALYZE analysis.metrics_daily;

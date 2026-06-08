-- Indexes supporting the per-project rollup refresh from migration 015.
-- Without these the DISTINCT ON dedupe falls back to a parallel sequential
-- scan over the whole post_insight table (8M+ rows on prod), which times out
-- past a couple of minutes for the larger projects.
--
-- The existing partial index `idx_post_insight_project_relevant_dedupe_latest`
-- only covers rows with `business_relevance_score >= 0.45`, but the refresh
-- pulls everything with relevance >= 0.30 OR source_kind in
-- ('focused_page','focused_profile'), so the planner cannot use it.
--
-- CREATE INDEX CONCURRENTLY so the build doesn't take an exclusive lock on
-- post_insight while the ingest pipeline is still inserting.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_post_insight_project_dedupe_v2
  ON analysis.post_insight (
    project_id,
    (COALESCE(NULLIF(upper((platform)::text), ''::text), 'UNKNOWN'::text)),
    (COALESCE(
       NULLIF((source_id)::text, ''::text),
       NULLIF((uap_metadata ->> 'post_id'::text), ''::text),
       NULLIF((uap_metadata ->> 'comment_id'::text), ''::text),
       NULLIF((uap_metadata ->> 'video_id'::text), ''::text),
       NULLIF((uap_metadata ->> 'url'::text), ''::text),
       (id)::text
    )),
    (COALESCE(updated_at, analyzed_at, ingested_at, created_at)) DESC NULLS LAST,
    created_at DESC NULLS LAST,
    id DESC
  )
  WHERE
    COALESCE(business_relevance_score, 0) >= 0.30
    OR COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}'::text[], '') IN ('focused_page', 'focused_profile');

ANALYZE analysis.post_insight;

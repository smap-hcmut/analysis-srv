-- Optimize analytics dashboard reads after business relevance gating.
--
-- The API base CTE now filters to business_relevance_score >= 0.45 before
-- deduping, then orders by platform/source identity and latest analysis time.
-- This partial expression index keeps that hot path small and ordered without
-- indexing the millions of low-relevance historical rows.
--
-- Production note: CONCURRENTLY avoids long write blocking on post_insight.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_post_insight_project_relevant_dedupe_latest
ON analysis.post_insight USING btree (
  project_id,
  (COALESCE(NULLIF(UPPER(platform::text), ''), 'UNKNOWN')),
  (COALESCE(
    NULLIF(source_id::text, ''),
    NULLIF((uap_metadata ->> 'post_id'), ''),
    NULLIF((uap_metadata ->> 'comment_id'), ''),
    NULLIF((uap_metadata ->> 'video_id'), ''),
    NULLIF((uap_metadata ->> 'url'), ''),
    id::text
  )),
  (COALESCE(updated_at, analyzed_at, ingested_at, created_at)) DESC NULLS LAST,
  created_at DESC NULLS LAST,
  id DESC
)
WHERE business_relevance_score >= 0.45;

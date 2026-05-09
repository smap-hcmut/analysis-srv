-- Speed up /api/v1/analytics/posts filters by platform + sentiment.
--
-- The posts endpoint pre-filters platform/sentiment before the dedupe CTE, so
-- this partial expression index lets PostgreSQL read the smallest relevant
-- slice before DISTINCT ON and ordering.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_post_insight_project_platform_sentiment_relevant_dedupe_latest
ON analysis.post_insight USING btree (
  project_id,
  (COALESCE(NULLIF(UPPER(platform::text), ''), 'UNKNOWN')),
  (UPPER(COALESCE(overall_sentiment::text, ''))),
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

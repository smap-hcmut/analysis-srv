-- One-shot dedupe of analysis.post_insight + unique constraint to keep it
-- deduped going forward.
--
-- Background: the consumer's persist path called repository.create() for
-- every analyzed UAP. The scheduler runs the analysis pipeline every ~3
-- minutes, so every post landed roughly 21 times per day. 8.2M-row table
-- on 2026-06-08; only ~400 unique posts per day across the active
-- campaigns. The mart's DISTINCT ON had to do a 95%+ dedupe pass on
-- every refresh, which timed out for the largest projects.
--
-- Apply order:
--   1. Deploy analysis-consumer change (usecase.create -> repository.upsert
--      with platform-aware match key). This stops *new* duplicates.
--   2. Run the dedupe DELETE below (off-peak, takes a while on 8M rows).
--   3. Add the UNIQUE INDEX CONCURRENTLY as a safety net.
--
-- DO NOT apply this migration until step 1 is rolled out — otherwise the
-- dedupe leaves only the latest existing copy and the consumer
-- immediately starts inserting fresh duplicates again.

BEGIN;
WITH ranked AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY project_id, platform, source_id
      ORDER BY analyzed_at DESC NULLS LAST,
               updated_at DESC NULLS LAST,
               created_at DESC NULLS LAST,
               id DESC
    ) AS rn
  FROM analysis.post_insight
  WHERE source_id IS NOT NULL AND source_id <> ''
)
DELETE FROM analysis.post_insight pi
USING ranked
WHERE pi.id = ranked.id AND ranked.rn > 1;
COMMIT;

-- Backstop. NULLS NOT DISTINCT keeps NULL/empty source_id rows out of the
-- uniqueness check — those rows are degenerate (no stable identity) and
-- the analytics dedupe already falls back to id::text for them.
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_post_insight_project_platform_source
  ON analysis.post_insight (project_id, platform, source_id)
  WHERE source_id IS NOT NULL AND source_id <> '';

ANALYZE analysis.post_insight;

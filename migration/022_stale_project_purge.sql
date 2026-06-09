-- One-off purge of analysis data tied to deleted campaigns/projects.
--
-- Background: analysis.post_insight retained ~7M rows from 13 soft-deleted
-- campaigns (12 projects) plus their derived mart/rollup slices. The dead
-- rows bloated the table to 19 GB and forced every refresh_project_rollups
-- and auto-ontology scan to skim past stale partitions, contributing to the
-- 2026-06-09 pool jams.
--
-- This migration captures the discovery + cleanup as a re-runnable script.
-- Production was purged on 2026-06-10 via /tmp/purge_pi2.sh on the postgres
-- VM (per-project chunked DELETE, 2 000 rows / 300 ms idle, followed by
-- VACUUM ANALYZE). The migration mirrors that work so DR rebuilds end at
-- the same row set.

-- 1. Stable snapshot of stale projects (campaigns or projects soft-deleted).
DROP TABLE IF EXISTS analysis.stale_project_ids;
CREATE TABLE analysis.stale_project_ids AS
SELECT DISTINCT
  p.id::text AS project_id,
  p.name      AS project_name,
  c.name      AS campaign_name,
  c.deleted_at AS campaign_deleted_at,
  p.deleted_at AS project_deleted_at
FROM project.projects p
LEFT JOIN project.campaigns c ON c.id = p.campaign_id
WHERE c.id IS NULL OR c.deleted_at IS NOT NULL OR p.deleted_at IS NOT NULL;
CREATE INDEX ON analysis.stale_project_ids (project_id);

-- 2. Companion list of survivors so the operator can sanity-check.
DROP TABLE IF EXISTS analysis.live_project_ids;
CREATE TABLE analysis.live_project_ids AS
SELECT
  p.id::text  AS project_id,
  p.name      AS project_name,
  c.name      AS campaign_name
FROM project.projects p
JOIN project.campaigns c ON c.id = p.campaign_id
WHERE c.deleted_at IS NULL AND p.deleted_at IS NULL;
CREATE INDEX ON analysis.live_project_ids (project_id);

-- 3. Small derived tables — single statement is fine; sub-second on prod.
DELETE FROM analysis.kpi_daily         WHERE project_id IN (SELECT project_id FROM analysis.stale_project_ids);
DELETE FROM analysis.metrics_daily     WHERE project_id IN (SELECT project_id FROM analysis.stale_project_ids);
DELETE FROM analysis.posts_recent_top  WHERE project_id IN (SELECT project_id FROM analysis.stale_project_ids);

-- 4. Knowledge artifacts under deleted campaigns.
DELETE FROM knowledge.messages
WHERE conversation_id::text IN (
  SELECT id::text FROM knowledge.conversations
  WHERE campaign_id::text IN (SELECT id::text FROM project.campaigns WHERE deleted_at IS NOT NULL)
);
DELETE FROM knowledge.conversations
WHERE campaign_id::text IN (SELECT id::text FROM project.campaigns WHERE deleted_at IS NOT NULL);

-- 5. analysis.post_insight: the heavy one. Bulk DELETE in one statement
-- starves kine on the shared Postgres (incident 2026-06-09). Do it with the
-- per-project chunked helper instead — see scripts/purge_stale_post_insight.sh
-- for the exact loop. Pseudo-equivalent SQL (psql client perspective):
--
--   FOR pid IN (SELECT project_id FROM analysis.stale_project_ids) LOOP
--     LOOP
--       DELETE FROM analysis.post_insight
--       WHERE id IN (
--         SELECT id FROM analysis.post_insight
--         WHERE project_id = pid LIMIT 2000
--       );
--       EXIT WHEN ROW_COUNT = 0;
--       PERFORM pg_sleep(0.3);
--     END LOOP;
--   END LOOP;

-- 6. Refresh derived state and shrink stats after the purge.
REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
VACUUM (ANALYZE) analysis.post_insight;
VACUUM (ANALYZE) analysis.kpi_daily;
VACUUM (ANALYZE) analysis.metrics_daily;
VACUUM (ANALYZE) analysis.posts_recent_top;
VACUUM (ANALYZE) analysis.latest_post_insight;

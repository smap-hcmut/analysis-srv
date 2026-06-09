-- One-shot dedupe of analysis.post_insight + unique constraint.
--
-- Background: the consumer's persist path called repository.create() for
-- every analyzed UAP. The scheduler runs the analysis pipeline every ~3
-- minutes, so every post landed roughly 21 times per day. 8.2M-row table
-- on 2026-06-08; only ~277k unique (project_id, platform, source_id)
-- combinations. The mart's DISTINCT ON had to do a 95%+ dedupe pass on
-- every refresh, which timed out for the largest projects.
--
-- Apply order (already done):
--   1. Deploy analysis-consumer change (usecase.create -> repository.upsert
--      with platform-aware match key). This stops *new* duplicates.
--
-- Apply order (THIS migration — partial, REQUIRES MAINTENANCE WINDOW):
--   2. Run the build_keepers block to capture the survivor id set.
--   3. Run the bulk DELETE in chunks. WARNING: the kine SQL-shim for K3s
--      shares this PostgreSQL instance (172.16.19.10:5432). A single
--      large DELETE on analysis.post_insight saturates WAL flushes and
--      starves kine writes; on 2026-06-09 a 33-min DELETE drove
--      apiserver VIP off the network. Use the chunked + throttled form
--      below (BATCH_SIZE 50k, SLEEP 2s) and watch `kubectl get nodes`.
--   4. Drop the staging _keepers table.
--   5. Add the UNIQUE INDEX CONCURRENTLY as a backstop.
--
-- Status on 2026-06-09: step 1 deployed (analysis-consumer
-- 260609-0025-upsert-safe). Step 3 ran for 33 min and removed ~1.79M
-- duplicate rows before being cancelled to protect kine. Remaining
-- ~6.2M duplicates were left in place — they are functionally harmless
-- (the mart's DISTINCT ON still picks the latest row) but make the
-- refresh slower than necessary for the five largest projects. Schedule
-- a maintenance window to finish the dedupe with the chunked form.


-- Step 2: build the keepers staging table. ~3-5 min on prod.
DROP TABLE IF EXISTS analysis._keepers;
CREATE TABLE analysis._keepers (
  id uuid PRIMARY KEY,
  project_id text NOT NULL,
  platform text,
  source_id text
);

INSERT INTO analysis._keepers (id, project_id, platform, source_id)
SELECT DISTINCT ON (project_id, platform, source_id)
  id, project_id, platform, source_id
FROM analysis.post_insight
WHERE source_id IS NOT NULL AND source_id <> ''
ORDER BY project_id, platform, source_id,
         analyzed_at DESC NULLS LAST,
         updated_at DESC NULLS LAST,
         created_at DESC NULLS LAST,
         id DESC;

CREATE INDEX IF NOT EXISTS _keepers_lookup
  ON analysis._keepers (project_id, platform, source_id);

ANALYZE analysis._keepers;


-- Step 3: chunked DELETE.
-- Run inside a `psql -f` loop OR a shell wrapper. Each DELETE chunk holds
-- a short transaction so kine WAL flushes stay bounded. Sleep between
-- chunks lets autovacuum catch up.
--
-- Pseudocode shell loop (recommended):
--   while true; do
--     DELETED=$(psql ... -At -c "
--       SET statement_timeout='90s';
--       WITH victims AS (
--         SELECT pi.id FROM analysis.post_insight pi
--          WHERE pi.source_id IS NOT NULL AND pi.source_id <> ''
--            AND NOT EXISTS (SELECT 1 FROM analysis._keepers k
--                             WHERE k.id = pi.id)
--          LIMIT 50000)
--       DELETE FROM analysis.post_insight pi USING victims v
--        WHERE pi.id = v.id;
--     ")
--     [ -z "$DELETED" ] && break
--     sleep 2
--   done
--
-- DO NOT run it as one large unbounded DELETE — that is what caused the
-- apiserver VIP outage on 2026-06-09.


-- Step 4: cleanup.
-- DROP TABLE analysis._keepers;
-- ANALYZE analysis.post_insight;


-- Step 5: backstop unique index. Add only after step 3 has driven the
-- remaining duplicate count to zero (otherwise CREATE INDEX
-- CONCURRENTLY fails at the validate phase).
-- CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_post_insight_project_platform_source
--   ON analysis.post_insight (project_id, platform, source_id)
--   WHERE source_id IS NOT NULL AND source_id <> '';

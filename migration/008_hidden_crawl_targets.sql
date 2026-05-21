-- Control-plane exclusions for flushed crawl targets.
--
-- Dashboard reads may use analysis.latest_post_insight, which is refreshed on a
-- schedule. Persisting hidden target IDs separately lets flush/delete take
-- effect immediately without waiting for a full materialized-view refresh.

CREATE TABLE IF NOT EXISTS analysis.hidden_crawl_targets (
  target_id uuid PRIMARY KEY,
  data_source_id uuid NULL,
  reason text NOT NULL DEFAULT 'stalker_flush',
  hidden_by text NOT NULL DEFAULT 'ingest-srv',
  hidden_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hidden_crawl_targets_data_source_id
  ON analysis.hidden_crawl_targets (data_source_id);

GRANT SELECT, INSERT, UPDATE ON analysis.hidden_crawl_targets TO analysis_prod;

CREATE OR REPLACE FUNCTION analysis.refresh_latest_post_insight()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = analysis, public
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_latest_post_insight() TO analysis_prod;

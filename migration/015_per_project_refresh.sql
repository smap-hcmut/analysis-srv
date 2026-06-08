-- Per-project rollup refresh.
--
-- Replaces the global TRUNCATE + rebuild chain (`refresh_latest_post_insight`)
-- that was timing out on every iteration once `analysis.post_insight` grew
-- past a few million rows. The old chain:
--   1. REFRESH MATERIALIZED VIEW CONCURRENTLY latest_post_insight   -- O(N) over post_insight
--   2. TRUNCATE kpi_daily; INSERT ... FROM latest_post_insight       -- depends on (1)
--   3. TRUNCATE posts_recent_top; INSERT ... FROM latest_post_insight -- depends on (1)
--   4. TRUNCATE metrics_daily; INSERT ... FROM latest_post_insight    -- depends on (1)
-- Once total cost exceeded statement_timeout (180s) the whole transaction
-- rolled back, leaving rollups stale and the UI empty even though ingestion
-- kept running.
--
-- New approach: bypass the materialized view entirely on the refresh side and
-- rewrite a single project's rollup rows with DISTINCT ON inline against
-- `analysis.post_insight`. Cost scales with one project's slice, not the
-- whole table. Functions are SECURITY DEFINER so the analysis-api role
-- (analysis_prod) can invoke them with the privileges needed to DELETE/INSERT
-- the rollup tables (which keep their existing owners).
--
-- Owner alignment: the new helpers must be applied as `postgres` so they run
-- with privileges sufficient to mutate rollups owned by `postgres` and
-- `analysis_master`. EXECUTE is granted to `analysis_prod`.

CREATE OR REPLACE FUNCTION analysis.refresh_kpi_daily_for_project(p_project_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  IF p_project_id IS NULL OR p_project_id = '' THEN
    RETURN;
  END IF;

  DELETE FROM analysis.kpi_daily WHERE project_id = p_project_id;

  INSERT INTO analysis.kpi_daily (
    project_id, bucket_date, mentions, sentiment_sum, engagement_sum,
    reach_sum, views_sum, likes_sum, comments_sum, shares_sum, refreshed_at
  )
  SELECT
    project_id,
    DATE_TRUNC('day', content_created_at)::DATE AS bucket_date,
    COUNT(*) AS mentions,
    SUM(COALESCE(overall_sentiment_score, 0)) AS sentiment_sum,
    SUM(COALESCE(engagement_score, 0)) AS engagement_sum,
    SUM(COALESCE(reach_estimate, 0)) AS reach_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'views')::BIGINT, 0)) AS views_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'likes')::BIGINT, 0)) AS likes_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'comments')::BIGINT, 0)) AS comments_sum,
    SUM(COALESCE((uap_metadata->'engagement'->>'shares')::BIGINT, 0)) AS shares_sum,
    NOW()
  FROM (
    SELECT DISTINCT ON (
      COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
      COALESCE(
        NULLIF(source_id, ''),
        NULLIF(uap_metadata->>'post_id', ''),
        NULLIF(uap_metadata->>'comment_id', ''),
        NULLIF(uap_metadata->>'video_id', ''),
        NULLIF(uap_metadata->>'url', ''),
        id::text
      )
    )
      project_id,
      content_created_at,
      overall_sentiment_score,
      engagement_score,
      reach_estimate,
      uap_metadata
    FROM analysis.post_insight
    WHERE project_id = p_project_id
      AND content_created_at IS NOT NULL
      AND (
        COALESCE(business_relevance_score, 0) >= 0.30
        OR COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
      )
    ORDER BY
      COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
      COALESCE(
        NULLIF(source_id, ''),
        NULLIF(uap_metadata->>'post_id', ''),
        NULLIF(uap_metadata->>'comment_id', ''),
        NULLIF(uap_metadata->>'video_id', ''),
        NULLIF(uap_metadata->>'url', ''),
        id::text
      ),
      COALESCE(updated_at, analyzed_at, ingested_at, created_at) DESC NULLS LAST,
      created_at DESC NULLS LAST,
      id DESC
  ) deduped
  GROUP BY project_id, DATE_TRUNC('day', content_created_at)::DATE;
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_kpi_daily_for_project(text) TO analysis_prod;


CREATE OR REPLACE FUNCTION analysis.refresh_posts_recent_top_for_project(p_project_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  IF p_project_id IS NULL OR p_project_id = '' THEN
    RETURN;
  END IF;

  DELETE FROM analysis.posts_recent_top WHERE project_id = p_project_id;

  INSERT INTO analysis.posts_recent_top (
    project_id, uap_id, source_id, platform, content_excerpt, author,
    content_created_at, overall_sentiment, sentiment_score, engagement_score,
    reach_estimate, url, uap_metadata, refreshed_at
  )
  SELECT
    project_id,
    COALESCE(uap_metadata->>'uap_id', source_id) AS uap_id,
    source_id,
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
    LEFT(content, 320) AS content_excerpt,
    COALESCE(
      uap_metadata->>'author_display_name',
      uap_metadata->>'author_username',
      uap_metadata->>'author'
    ) AS author,
    content_created_at,
    overall_sentiment,
    overall_sentiment_score AS sentiment_score,
    engagement_score,
    reach_estimate,
    COALESCE(
      uap_metadata->>'post_url',
      uap_metadata->>'url',
      uap_metadata->>'permalink_url',
      uap_metadata->>'original_url'
    ) AS url,
    uap_metadata,
    NOW()
  FROM (
    SELECT *,
           ROW_NUMBER() OVER (
             PARTITION BY project_id
             ORDER BY content_created_at DESC NULLS LAST,
                      engagement_score DESC NULLS LAST
           ) AS rn
    FROM (
      SELECT DISTINCT ON (
        COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
        COALESCE(
          NULLIF(source_id, ''),
          NULLIF(uap_metadata->>'post_id', ''),
          NULLIF(uap_metadata->>'comment_id', ''),
          NULLIF(uap_metadata->>'video_id', ''),
          NULLIF(uap_metadata->>'url', ''),
          id::text
        )
      ) *
      FROM analysis.post_insight
      WHERE project_id = p_project_id
        AND content_created_at IS NOT NULL
        AND (
          COALESCE(business_relevance_score, 0) >= 0.30
          OR COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
        )
      ORDER BY
        COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
        COALESCE(
          NULLIF(source_id, ''),
          NULLIF(uap_metadata->>'post_id', ''),
          NULLIF(uap_metadata->>'comment_id', ''),
          NULLIF(uap_metadata->>'video_id', ''),
          NULLIF(uap_metadata->>'url', ''),
          id::text
        ),
        COALESCE(updated_at, analyzed_at, ingested_at, created_at) DESC NULLS LAST,
        created_at DESC NULLS LAST,
        id DESC
    ) deduped
  ) ranked
  WHERE ranked.rn <= 1000;
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_posts_recent_top_for_project(text) TO analysis_prod;


CREATE OR REPLACE FUNCTION analysis.refresh_metrics_daily_for_project(p_project_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  IF p_project_id IS NULL OR p_project_id = '' THEN
    RETURN;
  END IF;

  DELETE FROM analysis.metrics_daily WHERE project_id = p_project_id;

  INSERT INTO analysis.metrics_daily (
    project_id, bucket_date, platform, sentiment,
    mentions, sentiment_score, engagement_sum, reach_sum, refreshed_at
  )
  SELECT
    project_id,
    DATE_TRUNC('day', content_created_at)::DATE AS bucket_date,
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
    COALESCE(NULLIF(UPPER(overall_sentiment), ''), 'UNKNOWN') AS sentiment,
    COUNT(*) AS mentions,
    AVG(COALESCE(overall_sentiment_score, 0)) AS sentiment_score,
    SUM(COALESCE(engagement_score, 0)) AS engagement_sum,
    SUM(COALESCE(reach_estimate, 0)) AS reach_sum,
    NOW()
  FROM (
    SELECT DISTINCT ON (
      COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
      COALESCE(
        NULLIF(source_id, ''),
        NULLIF(uap_metadata->>'post_id', ''),
        NULLIF(uap_metadata->>'comment_id', ''),
        NULLIF(uap_metadata->>'video_id', ''),
        NULLIF(uap_metadata->>'url', ''),
        id::text
      )
    )
      project_id,
      content_created_at,
      platform,
      overall_sentiment,
      overall_sentiment_score,
      engagement_score,
      reach_estimate
    FROM analysis.post_insight
    WHERE project_id = p_project_id
      AND content_created_at IS NOT NULL
      AND (
        COALESCE(business_relevance_score, 0) >= 0.30
        OR COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
      )
    ORDER BY
      COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
      COALESCE(
        NULLIF(source_id, ''),
        NULLIF(uap_metadata->>'post_id', ''),
        NULLIF(uap_metadata->>'comment_id', ''),
        NULLIF(uap_metadata->>'video_id', ''),
        NULLIF(uap_metadata->>'url', ''),
        id::text
      ),
      COALESCE(updated_at, analyzed_at, ingested_at, created_at) DESC NULLS LAST,
      created_at DESC NULLS LAST,
      id DESC
  ) deduped
  GROUP BY
    project_id,
    DATE_TRUNC('day', content_created_at)::DATE,
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
    COALESCE(NULLIF(UPPER(overall_sentiment), ''), 'UNKNOWN');
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_metrics_daily_for_project(text) TO analysis_prod;


-- Single entry point so the API loop only round-trips once per project.
CREATE OR REPLACE FUNCTION analysis.refresh_project_rollups(p_project_id text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  lock_key bigint;
  lock_acquired boolean;
BEGIN
  IF p_project_id IS NULL OR p_project_id = '' THEN
    RETURN;
  END IF;

  -- Per-project advisory lock keeps the loop from racing itself when a slow
  -- iteration overlaps the next tick. hashtextextended ensures the key fits
  -- bigint and gives stable hashing per project_id.
  lock_key := hashtextextended('analysis.refresh_project_rollups:' || p_project_id, 0);
  SELECT pg_try_advisory_xact_lock(lock_key) INTO lock_acquired;
  IF NOT lock_acquired THEN
    RAISE NOTICE 'refresh_project_rollups(%): another refresh in progress; skipping', p_project_id;
    RETURN;
  END IF;

  PERFORM analysis.refresh_kpi_daily_for_project(p_project_id);
  PERFORM analysis.refresh_posts_recent_top_for_project(p_project_id);
  PERFORM analysis.refresh_metrics_daily_for_project(p_project_id);
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_project_rollups(text) TO analysis_prod;

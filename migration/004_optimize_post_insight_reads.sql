-- Performance migration for heavy analytics dashboard reads.
--
-- Why:
-- - Dashboard queries filter by project_id and repeatedly dedupe by platform/source identity.
-- - Large campaigns can spill/sort heavily without composite indexes.
--
-- Notes:
-- - Uses IF NOT EXISTS to be safe for repeat runs.
-- - Non-destructive: only adds indexes.

CREATE INDEX IF NOT EXISTS idx_post_insight_project_platform_updated
ON analysis.post_insight (project_id, platform, updated_at DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_post_insight_project_source_updated
ON analysis.post_insight (project_id, source_id, updated_at DESC, created_at DESC)
WHERE source_id IS NOT NULL AND source_id <> '';

CREATE INDEX IF NOT EXISTS idx_post_insight_project_content_created
ON analysis.post_insight (project_id, content_created_at DESC);

CREATE INDEX IF NOT EXISTS idx_post_insight_project_post_id_updated
ON analysis.post_insight (
  project_id,
  (uap_metadata->>'post_id'),
  updated_at DESC,
  created_at DESC
)
WHERE (uap_metadata ? 'post_id');

CREATE INDEX IF NOT EXISTS idx_post_insight_project_comment_id_updated
ON analysis.post_insight (
  project_id,
  (uap_metadata->>'comment_id'),
  updated_at DESC,
  created_at DESC
)
WHERE (uap_metadata ? 'comment_id');

CREATE INDEX IF NOT EXISTS idx_post_insight_project_video_id_updated
ON analysis.post_insight (
  project_id,
  (uap_metadata->>'video_id'),
  updated_at DESC,
  created_at DESC
)
WHERE (uap_metadata ? 'video_id');

CREATE INDEX IF NOT EXISTS idx_post_insight_project_url_updated
ON analysis.post_insight (
  project_id,
  (uap_metadata->>'url'),
  updated_at DESC,
  created_at DESC
)
WHERE (uap_metadata ? 'url');

-- Revert script for Analytics Engine manual migration
-- WARNING: This will DROP tables and DELETE all data!

-- Drop indexes first
DROP INDEX IF EXISTS idx_post_analytics_job_id;
DROP INDEX IF EXISTS idx_post_analytics_fetch_status;
DROP INDEX IF EXISTS idx_post_analytics_task_type;
DROP INDEX IF EXISTS idx_post_analytics_error_code;

DROP INDEX IF EXISTS idx_crawl_errors_project_id;
DROP INDEX IF EXISTS idx_crawl_errors_error_code;
DROP INDEX IF EXISTS idx_crawl_errors_created_at;
DROP INDEX IF EXISTS idx_crawl_errors_job_id;

-- Drop tables
DROP TABLE IF EXISTS crawl_errors CASCADE;
DROP TABLE IF EXISTS post_analytics CASCADE;

-- Verify cleanup
SELECT 'Remaining tables:' as info;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('post_analytics', 'crawl_errors');

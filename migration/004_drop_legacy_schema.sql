-- ============================================================================
-- Migration 004: Drop Legacy Schema
-- ============================================================================
-- PREREQUISITE: 
--   1. Schema mới schema_analyst.post_schema_analyst đã chạy ổn định ≥ 2 tuần
--   2. Không còn service nào đọc/ghi schema_analyst.analyzed_posts
--   3. Đã backup toàn bộ data trong schema_analyst
--
-- BACKUP COMMAND (run before this migration):
--   pg_dump -h <host> -U <user> -d <database> -n schema_analyst -F c -f schema_analyst_backup_$(date +%Y%m%d).dump
--
-- ROLLBACK: Use migration/004_rollback.sql + restore from backup
-- ============================================================================

BEGIN;

-- Step 1: Verify no active connections to legacy table
DO $$
DECLARE
    active_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO active_count
    FROM pg_stat_activity
    WHERE query LIKE '%schema_analyst.analyzed_posts%'
      AND state = 'active'
      AND pid != pg_backend_pid();
    
    IF active_count > 0 THEN
        RAISE EXCEPTION 'Active connections detected on schema_analyst.analyzed_posts. Abort migration.';
    END IF;
END $$;

-- Step 2: Drop legacy table
DROP TABLE IF EXISTS schema_analyst.analyzed_posts CASCADE;

-- Step 3: Drop legacy schema (only if empty)
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'schema_analyst';
    
    IF table_count = 0 THEN
        DROP SCHEMA IF EXISTS schema_analyst CASCADE;
        RAISE NOTICE 'Schema schema_analyst dropped successfully';
    ELSE
        RAISE NOTICE 'Schema schema_analyst still contains % tables, not dropping', table_count;
    END IF;
END $$;

-- Step 4: Revoke permissions (if schema dropped)
-- REVOKE ALL ON SCHEMA schema_analyst FROM analyst_prod;
-- (Uncomment and replace analyst_prod if needed)

COMMIT;

-- ============================================================================
-- Verification Queries (run after migration)
-- ============================================================================
-- Check schema exists:
-- SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'schema_analyst';
-- Expected: 0 rows

-- Check table exists:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'schema_analyst' AND table_name = 'analyzed_posts';
-- Expected: 0 rows

-- Check new schema is working:
-- SELECT COUNT(*) FROM schema_analyst.post_schema_analyst;
-- Expected: > 0 rows

-- Migration: Drop legacy schema
-- CHẠY SAU KHI DEPLOY CODE MỚI VÀ VERIFY

-- 1. Drop legacy table
DROP TABLE IF EXISTS schema_analyst.analyzed_posts CASCADE;

-- 2. Drop legacy schema (nếu trống)
DROP SCHEMA IF EXISTS schema_analyst CASCADE;

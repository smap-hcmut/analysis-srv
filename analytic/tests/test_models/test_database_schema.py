"""Unit tests to validate database schema changes for crawler integration.

These tests validate the schema definitions without requiring a live database.
"""

import pytest
from sqlalchemy import inspect

from models.database import Base, PostAnalytics, CrawlError


class TestPostAnalyticsSchema:
    """Tests for PostAnalytics model schema."""

    def test_has_crawler_integration_fields(self):
        """PostAnalytics should have all 10 new crawler integration fields."""
        columns = {c.name for c in PostAnalytics.__table__.columns}

        # Batch context fields
        assert "job_id" in columns
        assert "batch_index" in columns
        assert "task_type" in columns

        # Crawler metadata fields
        assert "keyword_source" in columns
        assert "crawled_at" in columns
        assert "pipeline_version" in columns

        # Error tracking fields
        assert "fetch_status" in columns
        assert "fetch_error" in columns
        assert "error_code" in columns
        assert "error_details" in columns

    def test_project_id_is_nullable(self):
        """project_id should be nullable for dry-run tasks."""
        column = PostAnalytics.__table__.columns["project_id"]
        assert column.nullable is True

    def test_job_id_column_properties(self):
        """job_id should be VARCHAR(100), nullable, indexed."""
        column = PostAnalytics.__table__.columns["job_id"]
        assert str(column.type) == "VARCHAR(100)"
        assert column.nullable is True
        assert column.index is True

    def test_fetch_status_column_properties(self):
        """fetch_status should be VARCHAR(10), nullable, indexed, default 'success'."""
        column = PostAnalytics.__table__.columns["fetch_status"]
        assert str(column.type) == "VARCHAR(10)"
        assert column.nullable is True
        assert column.index is True
        assert column.default.arg == "success"

    def test_error_details_is_jsonb(self):
        """error_details should be JSONB type."""
        column = PostAnalytics.__table__.columns["error_details"]
        assert "JSONB" in str(column.type)

    def test_has_required_indexes(self):
        """PostAnalytics should have indexes on job_id, fetch_status, task_type, error_code."""
        indexes = {idx.name for idx in PostAnalytics.__table__.indexes}

        assert "idx_post_analytics_job_id" in indexes
        assert "idx_post_analytics_fetch_status" in indexes
        assert "idx_post_analytics_task_type" in indexes
        assert "idx_post_analytics_error_code" in indexes


class TestCrawlErrorSchema:
    """Tests for CrawlError model schema."""

    def test_table_name(self):
        """CrawlError table should be named 'crawl_errors'."""
        assert CrawlError.__tablename__ == "crawl_errors"

    def test_has_all_required_columns(self):
        """CrawlError should have all required columns."""
        columns = {c.name for c in CrawlError.__table__.columns}

        required_columns = {
            "id",
            "content_id",
            "project_id",
            "job_id",
            "platform",
            "error_code",
            "error_category",
            "error_message",
            "error_details",
            "permalink",
            "created_at",
        }

        assert required_columns.issubset(columns)

    def test_id_is_autoincrement(self):
        """id should be autoincrement primary key."""
        column = CrawlError.__table__.columns["id"]
        assert column.primary_key is True
        assert column.autoincrement is True

    def test_content_id_not_nullable(self):
        """content_id should not be nullable."""
        column = CrawlError.__table__.columns["content_id"]
        assert column.nullable is False

    def test_project_id_is_nullable(self):
        """project_id should be nullable for dry-run tasks."""
        column = CrawlError.__table__.columns["project_id"]
        assert column.nullable is True

    def test_error_code_not_nullable(self):
        """error_code should not be nullable."""
        column = CrawlError.__table__.columns["error_code"]
        assert column.nullable is False

    def test_error_category_not_nullable(self):
        """error_category should not be nullable."""
        column = CrawlError.__table__.columns["error_category"]
        assert column.nullable is False

    def test_has_required_indexes(self):
        """CrawlError should have indexes on project_id, error_code, created_at, job_id."""
        indexes = {idx.name for idx in CrawlError.__table__.indexes}

        assert "idx_crawl_errors_project_id" in indexes
        assert "idx_crawl_errors_error_code" in indexes
        assert "idx_crawl_errors_created_at" in indexes
        assert "idx_crawl_errors_job_id" in indexes


class TestMigrationScript:
    """Tests for migration script structure."""

    def test_migration_file_exists(self):
        """Migration file should exist."""
        import os

        migration_path = "migrations/versions/add_crawler_integration_fields.py"
        assert os.path.exists(migration_path)

    def test_migration_has_upgrade_and_downgrade(self):
        """Migration should have both upgrade and downgrade functions."""
        from migrations.versions import add_crawler_integration_fields as migration

        assert hasattr(migration, "upgrade")
        assert hasattr(migration, "downgrade")
        assert callable(migration.upgrade)
        assert callable(migration.downgrade)

    def test_migration_revision_info(self):
        """Migration should have revision identifiers."""
        from migrations.versions import add_crawler_integration_fields as migration

        assert hasattr(migration, "revision")
        assert hasattr(migration, "down_revision")
        assert migration.revision == "add_crawler_integration"

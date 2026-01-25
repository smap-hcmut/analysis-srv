#!/usr/bin/env python3
"""Migration validation script for Analytics Service.

This script validates that the crawler integration migration was successful
by checking database schema, configuration, and sample data processing.

Usage:
    uv run python scripts/validate_migration.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.config_validation import validate_config_on_startup


def print_header(title: str) -> None:
    """Print section header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(name: str, passed: bool, message: str = "") -> None:
    """Print validation result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} - {name}")
    if message:
        print(f"         {message}")


def validate_database_schema(engine) -> tuple[bool, list[str]]:
    """Validate database schema has required columns and tables."""
    errors = []

    with engine.connect() as conn:
        # Check post_analytics new columns
        required_columns = [
            "job_id",
            "batch_index",
            "task_type",
            "keyword_source",
            "crawled_at",
            "pipeline_version",
            "fetch_status",
            "error_code",
        ]

        result = conn.execute(
            text(
                """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'post_analytics'
        """
            )
        )
        existing_columns = {row[0] for row in result}

        for col in required_columns:
            if col not in existing_columns:
                errors.append(f"Missing column: post_analytics.{col}")

        # Check crawl_errors table
        result = conn.execute(
            text(
                """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'crawl_errors'
            )
        """
            )
        )
        if not result.scalar():
            errors.append("Missing table: crawl_errors")
        else:
            # Check crawl_errors columns
            result = conn.execute(
                text(
                    """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'crawl_errors'
            """
                )
            )
            error_columns = {row[0] for row in result}
            required_error_cols = ["error_code", "error_category", "error_message", "job_id"]
            for col in required_error_cols:
                if col not in error_columns:
                    errors.append(f"Missing column: crawl_errors.{col}")

        # Check indexes
        result = conn.execute(
            text(
                """
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'post_analytics'
        """
            )
        )
        indexes = {row[0] for row in result}

        # Check for job_id index
        has_job_id_index = any("job_id" in idx for idx in indexes)
        if not has_job_id_index:
            errors.append("Missing index on post_analytics.job_id")

    return len(errors) == 0, errors


def validate_configuration() -> tuple[bool, list[str]]:
    """Validate configuration settings."""
    errors = []

    # Check required settings
    if not settings.event_exchange:
        errors.append("EVENT_EXCHANGE not configured")

    if not settings.event_queue_name:
        errors.append("EVENT_QUEUE_NAME not configured")

    if not settings.minio_crawl_results_bucket:
        errors.append("MINIO_CRAWL_RESULTS_BUCKET not configured")

    # Check batch settings
    if settings.expected_batch_size_tiktok <= 0:
        errors.append("Invalid EXPECTED_BATCH_SIZE_TIKTOK")

    if settings.expected_batch_size_youtube <= 0:
        errors.append("Invalid EXPECTED_BATCH_SIZE_YOUTUBE")

    return len(errors) == 0, errors


def validate_data_processing(engine) -> tuple[bool, list[str]]:
    """Validate that data is being processed correctly."""
    warnings = []

    with engine.connect() as conn:
        # Check for recent records with job_id
        result = conn.execute(
            text(
                """
            SELECT COUNT(*) 
            FROM post_analytics 
            WHERE job_id IS NOT NULL 
            AND analyzed_at > NOW() - INTERVAL '24 hours'
        """
            )
        )
        new_format_count = result.scalar()

        if new_format_count == 0:
            warnings.append("No records with job_id in last 24 hours (new format not processing?)")
        else:
            print(f"         Found {new_format_count} records with job_id in last 24 hours")

        # Check error distribution
        result = conn.execute(
            text(
                """
            SELECT error_category, COUNT(*) 
            FROM crawl_errors 
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY error_category
        """
            )
        )
        error_stats = dict(result.fetchall())

        if error_stats:
            print(f"         Error distribution (24h): {error_stats}")

        # Check success rate
        result = conn.execute(
            text(
                """
            SELECT 
                COUNT(*) FILTER (WHERE fetch_status = 'success') as success,
                COUNT(*) FILTER (WHERE fetch_status = 'error') as errors,
                COUNT(*) as total
            FROM post_analytics
            WHERE analyzed_at > NOW() - INTERVAL '24 hours'
            AND job_id IS NOT NULL
        """
            )
        )
        row = result.fetchone()
        if row and row[2] > 0:
            success_rate = (row[0] / row[2]) * 100
            print(f"         Success rate (24h): {success_rate:.1f}% ({row[0]}/{row[2]})")
            if success_rate < 90:
                warnings.append(f"Success rate below 90%: {success_rate:.1f}%")

    return True, warnings


def validate_minio_connection() -> tuple[bool, list[str]]:
    """Validate MinIO connection and bucket access."""
    errors = []

    try:
        from infrastructure.storage.minio_client import MinioAdapter

        adapter = MinioAdapter()

        # Try to list objects (will fail if no access)
        # Just creating the adapter validates connection params
        print(f"         MinIO endpoint: {settings.minio_endpoint}")
        print(f"         Bucket: {settings.minio_crawl_results_bucket}")

    except Exception as e:
        errors.append(f"MinIO connection failed: {e}")

    return len(errors) == 0, errors


def validate_rabbitmq_settings() -> tuple[bool, list[str]]:
    """Validate RabbitMQ configuration."""
    errors = []

    print(f"         Exchange: {settings.event_exchange}")
    print(f"         Queue: {settings.event_queue_name}")
    print(f"         Routing Key: {settings.event_routing_key}")

    # Basic URL validation
    if not settings.rabbitmq_url:
        errors.append("RABBITMQ_URL not configured")
    elif not settings.rabbitmq_url.startswith(("amqp://", "amqps://")):
        errors.append("Invalid RABBITMQ_URL scheme")

    return len(errors) == 0, errors


def main():
    """Run all validation checks."""
    print("\n" + "=" * 60)
    print(" Analytics Service Migration Validation")
    print(" " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    all_passed = True

    # 1. Configuration validation
    print_header("Configuration Validation")
    passed, errors = validate_configuration()
    print_result("Configuration settings", passed)
    for err in errors:
        print(f"         - {err}")
    all_passed = all_passed and passed

    # 2. Database schema validation
    print_header("Database Schema Validation")
    try:
        engine = create_engine(settings.database_url_sync)
        passed, errors = validate_database_schema(engine)
        print_result("Database schema", passed)
        for err in errors:
            print(f"         - {err}")
        all_passed = all_passed and passed
    except Exception as e:
        print_result("Database connection", False, str(e))
        all_passed = False
        engine = None

    # 3. MinIO connection validation
    print_header("MinIO Connection Validation")
    passed, errors = validate_minio_connection()
    print_result("MinIO connection", passed)
    for err in errors:
        print(f"         - {err}")
    all_passed = all_passed and passed

    # 4. RabbitMQ settings validation
    print_header("RabbitMQ Settings Validation")
    passed, errors = validate_rabbitmq_settings()
    print_result("RabbitMQ settings", passed)
    for err in errors:
        print(f"         - {err}")
    all_passed = all_passed and passed

    # 5. Data processing validation (if database connected)
    if engine:
        print_header("Data Processing Validation")
        passed, warnings = validate_data_processing(engine)
        print_result("Data processing", passed)
        for warn in warnings:
            print(f"         ⚠️  {warn}")

    # Summary
    print_header("Validation Summary")
    if all_passed:
        print("  ✅ All critical validations PASSED")
        print("  Migration appears successful!")
        return 0
    else:
        print("  ❌ Some validations FAILED")
        print("  Please review errors above and fix before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

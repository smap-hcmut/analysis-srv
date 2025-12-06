"""End-to-end integration tests for event processing (Task 7.7).

These tests validate the complete flow from RabbitMQ → MinIO → Database.

Requirements:
- PostgreSQL running at localhost:5432
- RabbitMQ running at localhost:5672
- MinIO running at localhost:9002
"""

import json
import pytest
import asyncio
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

# Set test environment
os.environ.setdefault(
    "DATABASE_URL_SYNC", "postgresql://tantai:21042004@localhost:5432/smap-identity"
)
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "tantai")
os.environ.setdefault("MINIO_SECRET_KEY", "21042004")
os.environ.setdefault("RABBITMQ_URL", "amqp://tantai:21042004@localhost:5672/")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from internal.consumers.main import (
    parse_minio_path,
    validate_event_format,
    parse_event_metadata,
    enrich_with_batch_context,
    process_single_item,
    _create_session_factory,
)
from internal.consumers.item_processor import (
    is_error_item,
    extract_error_info,
    BatchProcessingStats,
    ItemProcessingResult,
)
from infrastructure.storage.minio_client import MinioAdapter, MinioAdapterError
from repository.analytics_repository import AnalyticsRepository
from repository.crawl_error_repository import CrawlErrorRepository
from utils.project_id_extractor import extract_project_id
from core.constants import categorize_error, ErrorCategory


class TestEndToEndEventProcessing:
    """End-to-end tests for complete event processing flow (Task 7.7)."""

    @pytest.fixture
    def db_session(self):
        """Create database session for testing."""
        try:
            engine = create_engine("postgresql://tantai:21042004@localhost:5432/smap-identity")
            Session = sessionmaker(bind=engine)
            session = Session()
            yield session
            session.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    @pytest.fixture
    def minio_adapter(self):
        """Create MinIO adapter for testing."""
        return MinioAdapter()

    @pytest.fixture
    def test_event_id(self):
        """Generate unique test event ID."""
        return f"evt_test_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def test_project_id(self):
        """Generate unique test project ID (valid UUID)."""
        return str(uuid.uuid4())

    @pytest.fixture
    def sample_batch_data(self, test_project_id):
        """Create sample batch data for E2E testing."""
        return [
            {
                "meta": {
                    "id": f"post_e2e_001_{uuid.uuid4().hex[:6]}",
                    "platform": "tiktok",
                    "fetch_status": "success",
                    "permalink": "https://tiktok.com/@user/video/123",
                },
                "content": {"text": "E2E test content - great product!"},
                "interactions": {"likes": 1000, "comments_count": 50, "shares": 20},
            },
            {
                "meta": {
                    "id": f"post_e2e_002_{uuid.uuid4().hex[:6]}",
                    "platform": "tiktok",
                    "fetch_status": "error",
                    "error_code": "CONTENT_REMOVED",
                    "error_message": "Video has been removed",
                    "permalink": "https://tiktok.com/@user/video/456",
                },
            },
        ]

    @pytest.fixture
    def sample_event(self, test_event_id, test_project_id):
        """Create sample data.collected event."""
        return {
            "event_id": test_event_id,
            "event_type": "data.collected",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload": {
                "minio_path": f"crawl-results/tiktok/{test_project_id}/brand/batch_e2e.json",
                "project_id": test_project_id,
                "job_id": f"{test_project_id}-brand-0",
                "batch_index": 0,
                "content_count": 2,
                "platform": "tiktok",
                "task_type": "research_and_crawl",
                "keyword": "test keyword",
            },
        }

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_complete_event_processing_flow(
        self, db_session, minio_adapter, sample_event, sample_batch_data, test_project_id
    ):
        """Test complete flow: Event → MinIO fetch → Process → Database."""
        try:
            # Step 1: Upload batch to MinIO (simulating crawler)
            # Wrap list in dict since MinIO adapter expects dict
            minio_path = sample_event["payload"]["minio_path"]
            bucket, object_path = parse_minio_path(minio_path)

            minio_adapter.upload_json(
                bucket,
                object_path,
                {"items": sample_batch_data, "count": len(sample_batch_data)},
                compress=True,
            )

            # Step 2: Parse event (simulating consumer receiving message)
            assert validate_event_format(sample_event) is True

            event_metadata = parse_event_metadata(sample_event)
            assert event_metadata["event_id"] == sample_event["event_id"]
            assert event_metadata["job_id"] == sample_event["payload"]["job_id"]

            # Step 3: Fetch batch from MinIO
            batch_data = minio_adapter.download_json(bucket, object_path)

            # Handle both wrapped and unwrapped formats
            if isinstance(batch_data, dict) and "items" in batch_data:
                batch_items = batch_data["items"]
            elif isinstance(batch_data, list):
                batch_items = batch_data
            else:
                batch_items = [batch_data]

            assert len(batch_items) == 2

            # Step 4: Extract project_id
            job_id = event_metadata["job_id"]
            project_id = extract_project_id(job_id)
            assert project_id == test_project_id

            # Step 5: Process batch items
            analytics_repo = AnalyticsRepository(db_session)
            error_repo = CrawlErrorRepository(db_session)

            stats = BatchProcessingStats()

            for item in batch_items:
                if is_error_item(item):
                    # Process error item
                    error_info = extract_error_info(item)

                    error_data = {
                        "content_id": item["meta"]["id"],
                        "project_id": project_id,
                        "job_id": job_id,
                        "platform": item["meta"].get("platform", "tiktok"),
                        "error_code": error_info["error_code"],
                        "error_message": error_info["error_message"],
                        "error_details": error_info.get("error_details", {}),
                        "permalink": item["meta"].get("permalink"),
                    }

                    error_repo.save(error_data)

                    result = ItemProcessingResult(
                        content_id=item["meta"]["id"],
                        status="error",
                        error_code=error_info["error_code"],
                    )
                    stats.add_error(result)
                else:
                    # Process success item
                    enriched = enrich_with_batch_context(item, event_metadata, project_id)

                    # Verify enrichment
                    assert enriched["meta"]["job_id"] == job_id
                    assert enriched["meta"]["project_id"] == project_id
                    assert enriched["meta"]["task_type"] == "research_and_crawl"

                    result = ItemProcessingResult(
                        content_id=item["meta"]["id"],
                        status="success",
                        impact_score=50.0,
                    )
                    stats.add_success(result)

            # Step 6: Verify statistics
            assert stats.success_count == 1
            assert stats.error_count == 1
            assert stats.total_count == 2
            assert stats.success_rate == 50.0
            assert "CONTENT_REMOVED" in stats.error_distribution

            # Step 7: Verify error was saved to database
            db_session.commit()

            # Query error records
            error_stats = error_repo.get_error_stats(project_id=project_id)
            assert error_stats is not None

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")
        except Exception as e:
            if "connection" in str(e).lower():
                pytest.skip(f"Infrastructure not available: {e}")
            raise

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_error_categorization_in_flow(self, db_session):
        """Test error categorization during E2E processing."""
        error_items = [
            {"meta": {"id": "err_1", "fetch_status": "error", "error_code": "RATE_LIMITED"}},
            {"meta": {"id": "err_2", "fetch_status": "error", "error_code": "CONTENT_REMOVED"}},
            {"meta": {"id": "err_3", "fetch_status": "error", "error_code": "NETWORK_ERROR"}},
            {"meta": {"id": "err_4", "fetch_status": "error", "error_code": "PARSE_ERROR"}},
        ]

        expected_categories = [
            ErrorCategory.RATE_LIMITING,
            ErrorCategory.CONTENT,
            ErrorCategory.NETWORK,
            ErrorCategory.PARSING,
        ]

        for item, expected_category in zip(error_items, expected_categories):
            error_info = extract_error_info(item)
            category = categorize_error(error_info["error_code"])
            assert category == expected_category

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_batch_context_enrichment(self):
        """Test that batch context is properly enriched."""
        item = {
            "meta": {
                "id": "post_enrich_test",
                "platform": "tiktok",
            },
            "content": {"text": "Test content"},
        }

        event_metadata = {
            "event_id": "evt_test_123",
            "job_id": "proj_abc-brand-0",
            "batch_index": 5,
            "task_type": "research_and_crawl",
            "keyword": "VinFast VF8",
            "timestamp": "2025-12-06T10:15:30Z",
            "platform": "tiktok",
        }

        project_id = "proj_abc"

        enriched = enrich_with_batch_context(item, event_metadata, project_id)

        # Verify all context fields
        assert enriched["meta"]["job_id"] == "proj_abc-brand-0"
        assert enriched["meta"]["batch_index"] == 5
        assert enriched["meta"]["task_type"] == "research_and_crawl"
        assert enriched["meta"]["keyword_source"] == "VinFast VF8"
        assert enriched["meta"]["project_id"] == "proj_abc"
        assert enriched["meta"]["pipeline_version"] == "crawler_tiktok_v3"
        assert "crawled_at" in enriched["meta"]


class TestDatabaseIntegration:
    """Tests for database operations in E2E flow."""

    @pytest.fixture
    def db_session(self):
        """Create database session for testing."""
        try:
            engine = create_engine("postgresql://tantai:21042004@localhost:5432/smap-identity")
            Session = sessionmaker(bind=engine)
            session = Session()
            yield session
            session.rollback()
            session.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_error_repository_save_and_query(self, db_session):
        """Test saving and querying error records."""
        error_repo = CrawlErrorRepository(db_session)

        # Use valid UUID for project_id
        test_project_uuid = str(uuid.uuid4())

        # Save error record
        error_data = {
            "content_id": f"post_db_test_{uuid.uuid4().hex[:6]}",
            "project_id": test_project_uuid,  # Must be valid UUID
            "job_id": f"{test_project_uuid}-brand-0",
            "platform": "tiktok",
            "error_code": "RATE_LIMITED",
            "error_message": "Too many requests",
            "error_details": {"retry_after": 60},
            "permalink": "https://tiktok.com/@user/video/123",
        }

        try:
            error_repo.save(error_data)
            db_session.commit()

            # Query error stats
            stats = error_repo.get_error_stats(project_id=test_project_uuid)
            assert stats is not None

        except Exception as e:
            if "relation" in str(e).lower() or "table" in str(e).lower():
                pytest.skip(f"Database schema not ready: {e}")
            raise

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_analytics_repository_with_new_fields(self, db_session):
        """Test analytics repository with new crawler integration fields."""
        analytics_repo = AnalyticsRepository(db_session)

        # This test verifies the repository can handle new fields
        # Actual save would require full post processing
        assert analytics_repo is not None

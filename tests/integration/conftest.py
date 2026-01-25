"""Pytest configuration for integration tests.

This module provides fixtures and configuration for integration tests
that require external services (PostgreSQL, RabbitMQ, MinIO).
"""

import os
import pytest

# Set test environment variables before importing application modules
os.environ.setdefault(
    "DATABASE_URL_SYNC", "postgresql://tantai:21042004@localhost:5432/smap-identity"
)
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://tantai:21042004@localhost:5432/smap-identity"
)
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "tantai")
os.environ.setdefault("MINIO_SECRET_KEY", "21042004")
os.environ.setdefault("RABBITMQ_URL", "amqp://tantai:21042004@localhost:5672/")


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring external services"
    )
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "load: mark test as load test")


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return {
        "database_url": os.environ.get("DATABASE_URL_SYNC"),
        "minio_endpoint": os.environ.get("MINIO_ENDPOINT"),
        "minio_access_key": os.environ.get("MINIO_ACCESS_KEY"),
        "minio_secret_key": os.environ.get("MINIO_SECRET_KEY"),
        "rabbitmq_url": os.environ.get("RABBITMQ_URL"),
        "test_bucket": "crawl-results",
    }


@pytest.fixture(scope="session")
def ensure_minio_bucket(test_config):
    """Ensure test bucket exists in MinIO."""
    try:
        from minio import Minio

        client = Minio(
            test_config["minio_endpoint"].replace("http://", "").replace("https://", ""),
            access_key=test_config["minio_access_key"],
            secret_key=test_config["minio_secret_key"],
            secure=test_config["minio_endpoint"].startswith("https://"),
        )

        bucket_name = test_config["test_bucket"]
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"Created test bucket: {bucket_name}")

        return bucket_name
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")

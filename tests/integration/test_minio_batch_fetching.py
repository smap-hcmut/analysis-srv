"""Integration tests for MinIO batch fetching (Task 7.5).

These tests validate the complete flow of fetching batch data from MinIO,
including compression/decompression and error handling.

Requirements:
- MinIO running at localhost:9002
- Bucket 'crawl-results' exists
"""

import json
import pytest
import os
from unittest.mock import patch, MagicMock

# Set test environment before importing modules
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "tantai")
os.environ.setdefault("MINIO_SECRET_KEY", "21042004")

from infrastructure.storage.minio_client import (
    MinioAdapter,
    MinioAdapterError,
    MinioObjectNotFoundError,
    MinioDecompressionError,
)
from internal.consumers.main import parse_minio_path


class TestMinIOBatchFetching:
    """Integration tests for MinIO batch fetching (Task 7.5)."""

    @pytest.fixture
    def minio_adapter(self):
        """Create MinIO adapter for testing."""
        return MinioAdapter()

    @pytest.fixture
    def sample_batch_data(self):
        """Sample batch data for testing."""
        return [
            {
                "meta": {
                    "id": "post_001",
                    "platform": "tiktok",
                    "fetch_status": "success",
                    "permalink": "https://tiktok.com/@user/video/123",
                },
                "content": {"text": "Great product review!"},
                "interactions": {"likes": 1000, "comments_count": 50, "shares": 20},
            },
            {
                "meta": {
                    "id": "post_002",
                    "platform": "tiktok",
                    "fetch_status": "success",
                    "permalink": "https://tiktok.com/@user/video/456",
                },
                "content": {"text": "Another amazing video"},
                "interactions": {"likes": 500, "comments_count": 25, "shares": 10},
            },
            {
                "meta": {
                    "id": "post_003",
                    "platform": "tiktok",
                    "fetch_status": "error",
                    "error_code": "RATE_LIMITED",
                    "error_message": "Too many requests",
                },
            },
        ]

    @pytest.fixture
    def test_bucket(self):
        """Test bucket name."""
        return "crawl-results"

    @pytest.fixture
    def test_object_path(self):
        """Test object path."""
        return "tiktok/test/batch_test_001.json"

    def test_parse_minio_path_valid(self):
        """Test parsing valid MinIO paths."""
        test_cases = [
            (
                "crawl-results/tiktok/2025/12/06/batch_001.json",
                "crawl-results",
                "tiktok/2025/12/06/batch_001.json",
            ),
            ("my-bucket/path/to/file.json", "my-bucket", "path/to/file.json"),
            ("bucket/single.json", "bucket", "single.json"),
        ]

        for minio_path, expected_bucket, expected_path in test_cases:
            bucket, path = parse_minio_path(minio_path)
            assert bucket == expected_bucket, f"Failed for {minio_path}"
            assert path == expected_path, f"Failed for {minio_path}"

    def test_parse_minio_path_invalid(self):
        """Test parsing invalid MinIO paths."""
        invalid_paths = [
            "",
            "no-slash",
            "/leading-slash/path",
        ]

        for invalid_path in invalid_paths:
            with pytest.raises(ValueError):
                parse_minio_path(invalid_path)

    @pytest.mark.integration
    def test_upload_and_download_json_uncompressed(
        self, minio_adapter, sample_batch_data, test_bucket
    ):
        """Test uploading and downloading uncompressed JSON."""
        object_path = "test/integration/uncompressed_batch.json"

        try:
            # Upload without compression
            upload_result = minio_adapter.upload_json(
                test_bucket,
                object_path,
                {"items": sample_batch_data},
                compress=False,
            )

            assert upload_result["bucket"] == test_bucket
            assert upload_result["path"] == object_path
            assert not upload_result["compressed"]

            # Download and verify
            downloaded = minio_adapter.download_json(test_bucket, object_path)
            assert "items" in downloaded
            assert len(downloaded["items"]) == 3
            assert downloaded["items"][0]["meta"]["id"] == "post_001"

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_upload_and_download_json_compressed(
        self, minio_adapter, sample_batch_data, test_bucket
    ):
        """Test uploading and downloading compressed JSON."""
        object_path = "test/integration/compressed_batch.json"

        # Create larger data to ensure compression kicks in
        large_batch = sample_batch_data * 100  # Repeat to exceed min compression size

        try:
            # Upload with compression
            upload_result = minio_adapter.upload_json(
                test_bucket,
                object_path,
                {"items": large_batch},
                compress=True,
            )

            assert upload_result["bucket"] == test_bucket
            assert upload_result["path"] == object_path
            # Compression should be applied for large data
            if upload_result["original_size"] > 1024:
                assert upload_result["compressed"]

            # Download and verify auto-decompression
            downloaded = minio_adapter.download_json(test_bucket, object_path)
            assert "items" in downloaded
            assert len(downloaded["items"]) == len(large_batch)

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_download_nonexistent_object(self, minio_adapter, test_bucket):
        """Test downloading non-existent object raises proper error."""
        try:
            with pytest.raises(MinioObjectNotFoundError):
                minio_adapter.download_json(test_bucket, "nonexistent/path/file.json")
        except MinioAdapterError as e:
            if "NoSuchBucket" in str(e):
                pytest.skip(f"Test bucket not available: {e}")
            raise

    @pytest.mark.integration
    def test_batch_fetching_flow(self, minio_adapter, sample_batch_data, test_bucket):
        """Test complete batch fetching flow as used in event processing."""
        # Simulate the flow from event processing
        minio_path = f"{test_bucket}/tiktok/proj_test/brand/batch_flow_test.json"

        try:
            # Step 1: Parse MinIO path
            bucket, object_path = parse_minio_path(minio_path)
            assert bucket == test_bucket

            # Step 2: Upload test batch (simulating crawler) - wrap in dict for upload_json
            minio_adapter.upload_json(
                bucket,
                object_path,
                {"items": sample_batch_data},
                compress=True,
            )

            # Step 3: Download batch (as analytics service would)
            batch_data = minio_adapter.download_json(bucket, object_path)

            # Step 4: Verify batch structure
            if isinstance(batch_data, dict) and "items" in batch_data:
                batch_items = batch_data["items"]
            elif isinstance(batch_data, list):
                batch_items = batch_data
            else:
                batch_items = [batch_data]

            assert len(batch_items) == 3

            # Verify success items
            success_items = [
                item for item in batch_items if item.get("meta", {}).get("fetch_status") != "error"
            ]
            assert len(success_items) == 2

            # Verify error items
            error_items = [
                item for item in batch_items if item.get("meta", {}).get("fetch_status") == "error"
            ]
            assert len(error_items) == 1
            assert error_items[0]["meta"]["error_code"] == "RATE_LIMITED"

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")

    def test_download_json_validation(self, minio_adapter):
        """Test validation of bucket and path parameters."""
        with pytest.raises(ValueError):
            minio_adapter.download_json("", "path.json")

        with pytest.raises(ValueError):
            minio_adapter.download_json("bucket", "")

    @pytest.mark.integration
    def test_large_batch_handling(self, minio_adapter, test_bucket):
        """Test handling of large batches (50 items for TikTok)."""
        # Create 50-item batch
        large_batch = []
        for i in range(50):
            large_batch.append(
                {
                    "meta": {
                        "id": f"post_{i:03d}",
                        "platform": "tiktok",
                        "fetch_status": "success" if i % 10 != 0 else "error",
                        "error_code": "RATE_LIMITED" if i % 10 == 0 else None,
                    },
                    "content": {"text": f"Content for post {i}"},
                    "interactions": {"likes": i * 100, "comments_count": i * 10},
                }
            )

        object_path = "test/integration/large_batch_50.json"

        try:
            # Upload large batch wrapped in dict
            upload_result = minio_adapter.upload_json(
                test_bucket,
                object_path,
                {"items": large_batch, "count": 50},
                compress=True,
            )

            # Download and verify
            downloaded = minio_adapter.download_json(test_bucket, object_path)

            if isinstance(downloaded, dict) and "items" in downloaded:
                assert len(downloaded["items"]) == 50
                assert downloaded["count"] == 50
            elif isinstance(downloaded, list):
                assert len(downloaded) == 50
            else:
                pytest.fail("Unexpected response format")

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")


class TestMinIOErrorHandling:
    """Tests for MinIO error handling scenarios."""

    @pytest.fixture
    def minio_adapter(self):
        """Create MinIO adapter for testing."""
        return MinioAdapter()

    def test_invalid_json_handling(self):
        """Test handling of invalid JSON data."""
        adapter = MinioAdapter()

        # Mock the client to return invalid JSON
        with patch.object(adapter, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.read.return_value = b"not valid json"
            mock_response.close = MagicMock()
            mock_response.release_conn = MagicMock()

            mock_stat = MagicMock()
            mock_stat.metadata = {}

            mock_client.stat_object.return_value = mock_stat
            mock_client.get_object.return_value = mock_response

            with pytest.raises(MinioAdapterError) as exc_info:
                adapter.download_json("bucket", "invalid.json")

            assert "Invalid JSON" in str(exc_info.value)

    def test_connection_error_handling(self):
        """Test handling of connection errors."""
        # Create adapter with invalid endpoint
        with patch("infrastructure.storage.minio_client.settings") as mock_settings:
            mock_settings.minio_endpoint = "http://invalid-host:9999"
            mock_settings.minio_access_key = "test"
            mock_settings.minio_secret_key = "test"
            mock_settings.compression_default_level = 2

            adapter = MinioAdapter()

            with pytest.raises(MinioAdapterError):
                adapter.download_json("bucket", "path.json")

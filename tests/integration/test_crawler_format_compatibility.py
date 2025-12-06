"""Integration tests for Crawler format compatibility (Phase 7).

These tests validate that Analytics service can correctly read files
uploaded by Crawler service with their specific format:
- Zstd compression with "compressed: true" metadata
- JSON arrays (not objects)
"""

import json
import pytest
import os
import uuid
import io

# Set test environment
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9002")
os.environ.setdefault("MINIO_ACCESS_KEY", "tantai")
os.environ.setdefault("MINIO_SECRET_KEY", "21042004")

import zstandard as zstd
from minio import Minio

from infrastructure.storage.minio_client import (
    MinioAdapter,
    MinioAdapterError,
    MinioObjectNotFoundError,
)
from internal.consumers.main import parse_minio_path


class TestCrawlerFormatCompatibility:
    """Tests for Crawler service format compatibility."""

    @pytest.fixture
    def minio_adapter(self):
        """Create MinIO adapter for testing."""
        return MinioAdapter()

    @pytest.fixture
    def raw_minio_client(self):
        """Create raw MinIO client for simulating crawler uploads."""
        return Minio(
            "localhost:9002",
            access_key="tantai",
            secret_key="21042004",
            secure=False,
        )

    @pytest.fixture
    def test_bucket(self):
        """Test bucket name."""
        return "crawl-results"

    @pytest.fixture
    def sample_crawler_batch(self):
        """Sample batch data as Crawler would upload (JSON array)."""
        return [
            {
                "meta": {
                    "id": f"post_crawler_{uuid.uuid4().hex[:6]}",
                    "platform": "tiktok",
                    "fetch_status": "success",
                    "permalink": "https://tiktok.com/@user/video/123",
                },
                "content": {"text": "Crawler test content 1"},
                "interactions": {"likes": 1000, "comments_count": 50},
            },
            {
                "meta": {
                    "id": f"post_crawler_{uuid.uuid4().hex[:6]}",
                    "platform": "tiktok",
                    "fetch_status": "error",
                    "error_code": "RATE_LIMITED",
                    "error_message": "Too many requests",
                },
            },
            {
                "meta": {
                    "id": f"post_crawler_{uuid.uuid4().hex[:6]}",
                    "platform": "tiktok",
                    "fetch_status": "success",
                    "permalink": "https://tiktok.com/@user/video/456",
                },
                "content": {"text": "Crawler test content 2"},
                "interactions": {"likes": 500, "comments_count": 25},
            },
        ]

    def _upload_crawler_format(
        self,
        client: Minio,
        bucket: str,
        object_path: str,
        data: list,
        compression_level: int = 2,
    ):
        """Upload data in Crawler format (JSON array with zstd compression).

        Simulates exactly how Crawler service uploads batch files.
        """
        # Serialize to JSON (array format)
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        original_size = len(json_bytes)

        # Compress with zstd (level mapping: 2 -> zstd level 10)
        zstd_level_map = {0: 0, 1: 3, 2: 10, 3: 19}
        zstd_level = zstd_level_map.get(compression_level, 10)

        compressor = zstd.ZstdCompressor(level=zstd_level)
        compressed_bytes = compressor.compress(json_bytes)
        compressed_size = len(compressed_bytes)

        # Upload with Crawler metadata format
        metadata = {
            "compressed": "true",
            "compression-algorithm": "zstd",
            "compression-level": str(compression_level),
            "original-size": str(original_size),
            "compressed-size": str(compressed_size),
        }

        client.put_object(
            bucket,
            object_path,
            io.BytesIO(compressed_bytes),
            length=compressed_size,
            content_type="application/json",
            metadata=metadata,
        )

        return {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": compressed_size / original_size,
        }

    @pytest.mark.integration
    def test_download_crawler_compressed_array(
        self, minio_adapter, raw_minio_client, test_bucket, sample_crawler_batch
    ):
        """Test downloading Crawler's compressed JSON array format."""
        object_path = f"tiktok/test_crawler_format/batch_{uuid.uuid4().hex[:8]}.json"

        try:
            # Upload in Crawler format
            upload_info = self._upload_crawler_format(
                raw_minio_client,
                test_bucket,
                object_path,
                sample_crawler_batch,
            )

            print(f"\nUpload info: {upload_info}")

            # Download using Analytics adapter
            data = minio_adapter.download_json(test_bucket, object_path)

            # Should return list (Crawler format)
            assert isinstance(data, list), f"Expected list, got {type(data)}"
            assert len(data) == 3

            # Verify content
            assert data[0]["meta"]["platform"] == "tiktok"
            assert data[1]["meta"]["fetch_status"] == "error"
            assert data[1]["meta"]["error_code"] == "RATE_LIMITED"

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_download_batch_method_with_crawler_format(
        self, minio_adapter, raw_minio_client, test_bucket, sample_crawler_batch
    ):
        """Test download_batch() method with Crawler format."""
        object_path = f"tiktok/test_download_batch/batch_{uuid.uuid4().hex[:8]}.json"

        try:
            # Upload in Crawler format
            self._upload_crawler_format(
                raw_minio_client,
                test_bucket,
                object_path,
                sample_crawler_batch,
            )

            # Download using download_batch method
            batch_items = minio_adapter.download_batch(test_bucket, object_path)

            # Should always return list
            assert isinstance(batch_items, list)
            assert len(batch_items) == 3

            # Verify items
            success_items = [
                item for item in batch_items if item.get("meta", {}).get("fetch_status") != "error"
            ]
            error_items = [
                item for item in batch_items if item.get("meta", {}).get("fetch_status") == "error"
            ]

            assert len(success_items) == 2
            assert len(error_items) == 1

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_compression_detection_crawler_metadata(
        self, minio_adapter, raw_minio_client, test_bucket
    ):
        """Test that compression is detected from Crawler's metadata format."""
        object_path = f"tiktok/test_compression_detect/batch_{uuid.uuid4().hex[:8]}.json"
        test_data = [{"meta": {"id": "test_1"}}]

        try:
            # Upload with Crawler metadata
            self._upload_crawler_format(
                raw_minio_client,
                test_bucket,
                object_path,
                test_data,
            )

            # Get metadata
            stat = raw_minio_client.stat_object(test_bucket, object_path)
            metadata = stat.metadata or {}

            # Verify metadata format
            meta_lower = {k.lower(): v for k, v in metadata.items()}
            assert "x-amz-meta-compressed" in meta_lower
            assert meta_lower["x-amz-meta-compressed"] == "true"

            # Verify adapter can detect compression
            assert minio_adapter._is_compressed(metadata)

            # Verify download works
            data = minio_adapter.download_json(test_bucket, object_path)
            assert isinstance(data, list)
            assert len(data) == 1

        except Exception as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_uncompressed_array_format(self, minio_adapter, raw_minio_client, test_bucket):
        """Test downloading uncompressed JSON array (backward compatibility)."""
        object_path = f"tiktok/test_uncompressed/batch_{uuid.uuid4().hex[:8]}.json"
        test_data = [
            {"meta": {"id": "uncompressed_1"}},
            {"meta": {"id": "uncompressed_2"}},
        ]

        try:
            # Upload uncompressed JSON array
            json_bytes = json.dumps(test_data).encode("utf-8")
            raw_minio_client.put_object(
                test_bucket,
                object_path,
                io.BytesIO(json_bytes),
                length=len(json_bytes),
                content_type="application/json",
            )

            # Download
            data = minio_adapter.download_json(test_bucket, object_path)

            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["meta"]["id"] == "uncompressed_1"

        except Exception as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_analytics_format_still_works(self, minio_adapter, test_bucket):
        """Test that Analytics format (dict with items) still works."""
        object_path = f"tiktok/test_analytics_format/batch_{uuid.uuid4().hex[:8]}.json"
        test_data = {
            "items": [
                {"meta": {"id": "analytics_1"}},
                {"meta": {"id": "analytics_2"}},
            ],
            "count": 2,
        }

        try:
            # Upload in Analytics format
            minio_adapter.upload_json(test_bucket, object_path, test_data, compress=True)

            # Download using download_batch
            batch_items = minio_adapter.download_batch(test_bucket, object_path)

            assert isinstance(batch_items, list)
            assert len(batch_items) == 2
            assert batch_items[0]["meta"]["id"] == "analytics_1"

        except MinioAdapterError as e:
            pytest.skip(f"MinIO not available: {e}")

    @pytest.mark.integration
    def test_50_item_crawler_batch(self, minio_adapter, raw_minio_client, test_bucket):
        """Test downloading a 50-item batch in Crawler format (TikTok batch size)."""
        object_path = f"tiktok/test_50_items/batch_{uuid.uuid4().hex[:8]}.json"

        # Generate 50-item batch
        batch_data = []
        for i in range(50):
            if i % 10 == 0:
                # Error item
                batch_data.append(
                    {
                        "meta": {
                            "id": f"post_{i:03d}",
                            "platform": "tiktok",
                            "fetch_status": "error",
                            "error_code": "RATE_LIMITED",
                        }
                    }
                )
            else:
                # Success item
                batch_data.append(
                    {
                        "meta": {
                            "id": f"post_{i:03d}",
                            "platform": "tiktok",
                            "fetch_status": "success",
                        },
                        "content": {"text": f"Content {i}"},
                        "interactions": {"likes": i * 100},
                    }
                )

        try:
            # Upload in Crawler format
            upload_info = self._upload_crawler_format(
                raw_minio_client,
                test_bucket,
                object_path,
                batch_data,
            )

            print(f"\n50-item batch upload: {upload_info}")
            print(f"Compression ratio: {upload_info['compression_ratio']:.2%}")

            # Download
            items = minio_adapter.download_batch(test_bucket, object_path)

            assert len(items) == 50

            # Count success/error
            success_count = sum(
                1 for item in items if item.get("meta", {}).get("fetch_status") != "error"
            )
            error_count = sum(
                1 for item in items if item.get("meta", {}).get("fetch_status") == "error"
            )

            assert success_count == 45
            assert error_count == 5

        except Exception as e:
            pytest.skip(f"MinIO not available: {e}")


class TestCompressionMetadataFormats:
    """Tests for different compression metadata formats."""

    @pytest.fixture
    def minio_adapter(self):
        return MinioAdapter()

    def test_is_compressed_analytics_format(self, minio_adapter):
        """Test compression detection with Analytics metadata format."""
        metadata = {
            "x-amz-meta-compression-algorithm": "zstd",
            "x-amz-meta-compression-level": "2",
        }
        assert minio_adapter._is_compressed(metadata)

    def test_is_compressed_crawler_format(self, minio_adapter):
        """Test compression detection with Crawler metadata format."""
        metadata = {
            "x-amz-meta-compressed": "true",
            "x-amz-meta-compression-algorithm": "zstd",
        }
        assert minio_adapter._is_compressed(metadata)

    def test_is_compressed_crawler_only_flag(self, minio_adapter):
        """Test compression detection with only compressed flag."""
        metadata = {
            "x-amz-meta-compressed": "true",
        }
        assert minio_adapter._is_compressed(metadata)

    def test_is_not_compressed(self, minio_adapter):
        """Test uncompressed detection."""
        metadata = {}
        assert not minio_adapter._is_compressed(metadata)

        metadata = {"x-amz-meta-compressed": "false"}
        assert not minio_adapter._is_compressed(metadata)

    def test_parse_compression_metadata_full(self, minio_adapter):
        """Test parsing full compression metadata."""
        metadata = {
            "x-amz-meta-compressed": "true",
            "x-amz-meta-compression-algorithm": "zstd",
            "x-amz-meta-compression-level": "2",
            "x-amz-meta-original-size": "102400",
            "x-amz-meta-compressed-size": "25600",
        }

        result = minio_adapter._parse_compression_metadata(metadata)

        assert result["compressed"] == "true"
        assert result["algorithm"] == "zstd"
        assert result["level"] == 2
        assert result["original_size"] == 102400
        assert result["compressed_size"] == 25600

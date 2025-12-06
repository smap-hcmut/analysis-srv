"""Integration tests for MinIO storage with compression."""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from infrastructure.storage.minio_client import (
    MinioAdapter,
    MinioAdapterError,
    MinioDecompressionError,
)
from infrastructure.storage.constants import (
    METADATA_COMPRESSION_ALGORITHM,
    METADATA_COMPRESSION_LEVEL,
    METADATA_ORIGINAL_SIZE,
    METADATA_COMPRESSED_SIZE,
)


class TestDownloadJsonWithCompression:
    """Integration tests for download_json with compression support."""

    @pytest.fixture
    def adapter(self):
        """Create MinioAdapter with mocked MinIO client."""
        with patch("infrastructure.storage.minio_client.Minio") as mock_minio:
            adapter = MinioAdapter()
            adapter._mock_client = mock_minio.return_value
            return adapter

    def test_download_compressed_json(self, adapter):
        """Test downloading and decompressing a compressed JSON file."""
        # Prepare test data
        original_data = {"key": "value", "nested": {"a": 1, "b": 2}}
        original_bytes = json.dumps(original_data).encode("utf-8")
        compressed_bytes = adapter._compress_data(original_bytes)

        # Mock stat_object to return compression metadata
        mock_stat = MagicMock()
        mock_stat.metadata = {
            METADATA_COMPRESSION_ALGORITHM.lower(): "zstd",
            METADATA_COMPRESSION_LEVEL.lower(): "2",
            METADATA_ORIGINAL_SIZE.lower(): str(len(original_bytes)),
            METADATA_COMPRESSED_SIZE.lower(): str(len(compressed_bytes)),
        }
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object to return compressed data
        mock_response = MagicMock()
        mock_response.read.return_value = compressed_bytes
        adapter._client.get_object.return_value = mock_response

        # Execute
        result = adapter.download_json("test-bucket", "test/path.json")

        # Verify
        assert result == original_data
        adapter._client.stat_object.assert_called_once_with("test-bucket", "test/path.json")
        adapter._client.get_object.assert_called_once_with("test-bucket", "test/path.json")
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()

    def test_download_uncompressed_json(self, adapter):
        """Test downloading an uncompressed JSON file (backward compatibility)."""
        # Prepare test data
        original_data = {"key": "value", "list": [1, 2, 3]}
        original_bytes = json.dumps(original_data).encode("utf-8")

        # Mock stat_object with no compression metadata
        mock_stat = MagicMock()
        mock_stat.metadata = {}
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object to return uncompressed data
        mock_response = MagicMock()
        mock_response.read.return_value = original_bytes
        adapter._client.get_object.return_value = mock_response

        # Execute
        result = adapter.download_json("test-bucket", "test/path.json")

        # Verify
        assert result == original_data

    def test_download_json_with_none_metadata(self, adapter):
        """Test downloading when metadata is None."""
        original_data = {"test": "data"}
        original_bytes = json.dumps(original_data).encode("utf-8")

        # Mock stat_object with None metadata
        mock_stat = MagicMock()
        mock_stat.metadata = None
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object
        mock_response = MagicMock()
        mock_response.read.return_value = original_bytes
        adapter._client.get_object.return_value = mock_response

        # Execute - should treat as uncompressed
        result = adapter.download_json("test-bucket", "test/path.json")
        assert result == original_data

    def test_download_json_decompression_failure(self, adapter):
        """Test error handling when decompression fails."""
        # Mock stat_object with compression metadata
        mock_stat = MagicMock()
        mock_stat.metadata = {METADATA_COMPRESSION_ALGORITHM.lower(): "zstd"}
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object to return invalid compressed data
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid compressed data"
        adapter._client.get_object.return_value = mock_response

        # Execute - should raise MinioDecompressionError
        with pytest.raises(MinioDecompressionError):
            adapter.download_json("test-bucket", "test/path.json")

    def test_download_json_invalid_json(self, adapter):
        """Test error handling when JSON parsing fails."""
        # Mock stat_object with no compression
        mock_stat = MagicMock()
        mock_stat.metadata = {}
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object to return invalid JSON
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        adapter._client.get_object.return_value = mock_response

        # Execute - should raise MinioAdapterError
        with pytest.raises(MinioAdapterError, match="Invalid JSON"):
            adapter.download_json("test-bucket", "test/path.json")

    def test_download_json_array_format(self, adapter):
        """Test downloading JSON array format (Crawler format support).

        Since Phase 7 Crawler Format Compatibility, download_json() now supports
        both dict and list return types to handle Crawler's JSON array format.
        """
        # Mock stat_object with no compression
        mock_stat = MagicMock()
        mock_stat.metadata = {}
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object to return JSON array (Crawler format)
        test_array = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(test_array).encode("utf-8")
        adapter._client.get_object.return_value = mock_response

        # Execute - should return list (not raise error)
        result = adapter.download_json("test-bucket", "test/path.json")

        # Verify it returns the array
        assert isinstance(result, list)
        assert result == test_array

    def test_download_json_invalid_type(self, adapter):
        """Test error handling when JSON is not dict or list."""
        # Mock stat_object with no compression
        mock_stat = MagicMock()
        mock_stat.metadata = {}
        adapter._client.stat_object.return_value = mock_stat

        # Mock get_object to return JSON string (invalid type)
        mock_response = MagicMock()
        mock_response.read.return_value = b'"just a string"'
        adapter._client.get_object.return_value = mock_response

        # Execute - should raise MinioAdapterError for non-dict/list types
        with pytest.raises(MinioAdapterError, match="Expected JSON object"):
            adapter.download_json("test-bucket", "test/path.json")


class TestCompressionRoundtrip:
    """Test full compression/decompression roundtrip."""

    @pytest.fixture
    def adapter(self):
        """Create MinioAdapter with mocked MinIO client."""
        with patch("infrastructure.storage.minio_client.Minio"):
            return MinioAdapter()

    def test_json_roundtrip_small(self, adapter):
        """Test roundtrip with small JSON data."""
        original = {"id": 1, "name": "test"}
        json_bytes = json.dumps(original).encode("utf-8")
        compressed = adapter._compress_data(json_bytes)
        decompressed = adapter._decompress_data(compressed)
        result = json.loads(decompressed.decode("utf-8"))
        assert result == original

    def test_json_roundtrip_large(self, adapter):
        """Test roundtrip with large JSON data."""
        original = {"posts": [{"id": i, "content": f"Post content {i}" * 10} for i in range(100)]}
        json_bytes = json.dumps(original).encode("utf-8")
        compressed = adapter._compress_data(json_bytes)
        decompressed = adapter._decompress_data(compressed)
        result = json.loads(decompressed.decode("utf-8"))
        assert result == original
        # Verify compression actually reduced size
        assert len(compressed) < len(json_bytes)

    def test_json_roundtrip_unicode(self, adapter):
        """Test roundtrip with Unicode/Vietnamese content."""
        original = {
            "content": "Xin chào! Đây là nội dung tiếng Việt 🇻🇳",
            "author": "Nguyễn Văn A",
        }
        json_bytes = json.dumps(original, ensure_ascii=False).encode("utf-8")
        compressed = adapter._compress_data(json_bytes)
        decompressed = adapter._decompress_data(compressed)
        result = json.loads(decompressed.decode("utf-8"))
        assert result == original

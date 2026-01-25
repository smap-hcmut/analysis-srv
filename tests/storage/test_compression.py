"""Unit tests for MinIO compression/decompression functionality."""

import json
import pytest
from unittest.mock import MagicMock, patch

from infrastructure.storage.minio_client import MinioAdapter
from infrastructure.storage.constants import (
    METADATA_COMPRESSION_ALGORITHM,
    METADATA_COMPRESSION_LEVEL,
    METADATA_ORIGINAL_SIZE,
    METADATA_COMPRESSED_SIZE,
)


class TestCompressionMethods:
    """Test compression and decompression methods."""

    @pytest.fixture
    def adapter(self):
        """Create MinioAdapter with mocked MinIO client."""
        with patch("infrastructure.storage.minio_client.Minio"):
            return MinioAdapter()

    def test_compress_data_small(self, adapter):
        """Test compression with small data."""
        original = b"Hello, World!"
        compressed = adapter._compress_data(original)
        assert isinstance(compressed, bytes)
        assert len(compressed) > 0

    def test_compress_data_large(self, adapter):
        """Test compression with larger data - should achieve compression."""
        # Create repetitive data that compresses well
        original = b"test data " * 1000
        compressed = adapter._compress_data(original)
        assert isinstance(compressed, bytes)
        # Zstd should compress repetitive data significantly
        assert len(compressed) < len(original)

    def test_compress_data_with_custom_level(self, adapter):
        """Test compression with custom level."""
        original = b"test data " * 100
        compressed_level1 = adapter._compress_data(original, level=1)
        compressed_level3 = adapter._compress_data(original, level=3)
        assert isinstance(compressed_level1, bytes)
        assert isinstance(compressed_level3, bytes)
        # Higher level should produce smaller or equal output
        assert len(compressed_level3) <= len(compressed_level1)

    def test_decompress_data(self, adapter):
        """Test decompression of compressed data."""
        original = b"Hello, World! This is test data."
        compressed = adapter._compress_data(original)
        decompressed = adapter._decompress_data(compressed)
        assert decompressed == original

    def test_decompress_data_roundtrip(self, adapter):
        """Test compress/decompress roundtrip with various data sizes."""
        test_cases = [
            b"",  # Empty
            b"x",  # Single byte
            b"Hello",  # Small
            b"test " * 100,  # Medium
            json.dumps({"key": "value" * 100}).encode(),  # JSON-like
        ]
        for original in test_cases:
            compressed = adapter._compress_data(original)
            decompressed = adapter._decompress_data(compressed)
            assert decompressed == original, f"Roundtrip failed for: {original[:50]}"

    def test_decompress_invalid_data(self, adapter):
        """Test decompression with invalid data raises RuntimeError."""
        invalid_data = b"this is not compressed data"
        with pytest.raises(RuntimeError, match="Failed to decompress"):
            adapter._decompress_data(invalid_data)


class TestMetadataDetection:
    """Test compression metadata detection."""

    @pytest.fixture
    def adapter(self):
        """Create MinioAdapter with mocked MinIO client."""
        with patch("infrastructure.storage.minio_client.Minio"):
            return MinioAdapter()

    def test_is_compressed_with_zstd_metadata(self, adapter):
        """Test _is_compressed returns True for zstd metadata."""
        metadata = {METADATA_COMPRESSION_ALGORITHM: "zstd"}
        assert adapter._is_compressed(metadata) is True

    def test_is_compressed_with_lowercase_keys(self, adapter):
        """Test _is_compressed handles lowercase metadata keys."""
        metadata = {METADATA_COMPRESSION_ALGORITHM.lower(): "zstd"}
        assert adapter._is_compressed(metadata) is True

    def test_is_compressed_without_metadata(self, adapter):
        """Test _is_compressed returns False for empty metadata."""
        assert adapter._is_compressed({}) is False

    def test_is_compressed_with_other_algorithm(self, adapter):
        """Test _is_compressed returns False for non-zstd algorithm."""
        metadata = {METADATA_COMPRESSION_ALGORITHM: "gzip"}
        assert adapter._is_compressed(metadata) is False

    def test_get_compression_metadata_full(self, adapter):
        """Test _get_compression_metadata extracts all fields."""
        metadata = {
            METADATA_COMPRESSION_ALGORITHM: "zstd",
            METADATA_COMPRESSION_LEVEL: "2",
            METADATA_ORIGINAL_SIZE: "1000",
            METADATA_COMPRESSED_SIZE: "500",
        }
        result = adapter._get_compression_metadata(metadata)
        assert result["algorithm"] == "zstd"
        assert result["level"] == 2
        assert result["original_size"] == 1000
        assert result["compressed_size"] == 500

    def test_get_compression_metadata_partial(self, adapter):
        """Test _get_compression_metadata with partial metadata."""
        metadata = {METADATA_COMPRESSION_ALGORITHM: "zstd"}
        result = adapter._get_compression_metadata(metadata)
        assert result["algorithm"] == "zstd"
        assert "level" not in result
        assert "original_size" not in result

    def test_get_compression_metadata_empty(self, adapter):
        """Test _get_compression_metadata returns empty dict for no metadata."""
        result = adapter._get_compression_metadata({})
        assert result == {}


class TestBuildCompressionMetadata:
    """Test building compression metadata for uploads."""

    @pytest.fixture
    def adapter(self):
        """Create MinioAdapter with mocked MinIO client."""
        with patch("infrastructure.storage.minio_client.Minio"):
            return MinioAdapter()

    def test_build_compression_metadata(self, adapter):
        """Test _build_compression_metadata creates correct dict."""
        result = adapter._build_compression_metadata(
            original_size=1000,
            compressed_size=500,
            level=2,
        )
        assert result[METADATA_COMPRESSION_ALGORITHM] == "zstd"
        assert result[METADATA_COMPRESSION_LEVEL] == "2"
        assert result[METADATA_ORIGINAL_SIZE] == "1000"
        assert result[METADATA_COMPRESSED_SIZE] == "500"

    def test_build_compression_metadata_default_level(self, adapter):
        """Test _build_compression_metadata uses default level."""
        result = adapter._build_compression_metadata(
            original_size=1000,
            compressed_size=500,
        )
        # Should use config default (2)
        assert result[METADATA_COMPRESSION_LEVEL] == "2"


class TestBackwardCompatibility:
    """Test backward compatibility with uncompressed files."""

    @pytest.fixture
    def adapter(self):
        """Create MinioAdapter with mocked MinIO client."""
        with patch("infrastructure.storage.minio_client.Minio"):
            return MinioAdapter()

    def test_no_metadata_means_uncompressed(self, adapter):
        """Test that missing metadata is treated as uncompressed."""
        assert adapter._is_compressed({}) is False

    def test_empty_algorithm_means_uncompressed(self, adapter):
        """Test that empty algorithm is treated as uncompressed."""
        metadata = {METADATA_COMPRESSION_ALGORITHM: ""}
        assert adapter._is_compressed(metadata) is False

    def test_none_metadata_handling(self, adapter):
        """Test handling of None-like metadata values."""
        # Empty dict should work
        assert adapter._is_compressed({}) is False
        # Metadata with None values should not crash
        metadata = {METADATA_COMPRESSION_ALGORITHM.lower(): None}
        # This should return False, not crash
        assert adapter._is_compressed(metadata) is False

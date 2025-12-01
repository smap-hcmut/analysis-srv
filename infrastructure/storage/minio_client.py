"""MinIO storage adapter for reading Atomic JSON posts.

This module wraps the MinIO Python SDK behind a small adapter so that
callers (e.g. orchestrated consumers) can fetch JSON objects from MinIO
without depending directly on the SDK.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import zstandard as zstd
from minio import Minio  # type: ignore

from core.config import settings
from core.logger import logger
from infrastructure.storage.constants import (
    METADATA_COMPRESSED_SIZE,
    METADATA_COMPRESSION_ALGORITHM,
    METADATA_COMPRESSION_LEVEL,
    METADATA_ORIGINAL_SIZE,
)


class MinioAdapter:
    """Thin wrapper around MinIO client to download JSON objects."""

    def __init__(self) -> None:
        self._client = Minio(
            settings.minio_endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_endpoint.startswith("https://"),
        )
        self._compressor = zstd.ZstdCompressor(level=settings.compression_default_level)
        self._decompressor = zstd.ZstdDecompressor()

    def _compress_data(self, data: bytes, level: Optional[int] = None) -> bytes:
        """Compress data using Zstd algorithm.

        Args:
            data: Raw bytes to compress.
            level: Compression level (0-22). Uses config default if not specified.

        Returns:
            Compressed bytes.
        """
        if level is not None and level != settings.compression_default_level:
            compressor = zstd.ZstdCompressor(level=level)
            return compressor.compress(data)
        return self._compressor.compress(data)

    def _decompress_data(self, data: bytes) -> bytes:
        """Decompress Zstd-compressed data.

        Args:
            data: Compressed bytes.

        Returns:
            Decompressed bytes.

        Raises:
            RuntimeError: If decompression fails.
        """
        try:
            return self._decompressor.decompress(data)
        except zstd.ZstdError as exc:
            raise RuntimeError(f"Failed to decompress data: {exc}") from exc

    def _is_compressed(self, metadata: Dict[str, str]) -> bool:
        """Check if object metadata indicates compression.

        Args:
            metadata: Object metadata dictionary from MinIO.

        Returns:
            True if the object is compressed, False otherwise.
        """
        algorithm = self._get_compression_metadata(metadata).get("algorithm")
        return algorithm == "zstd"

    def _get_compression_metadata(self, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Extract compression metadata from object metadata.

        Args:
            metadata: Object metadata dictionary from MinIO.

        Returns:
            Dictionary with compression info (algorithm, level, original_size, compressed_size).
            Empty dict if no compression metadata found.
        """
        return self._parse_compression_metadata(metadata)

    def _build_compression_metadata(
        self,
        original_size: int,
        compressed_size: int,
        level: Optional[int] = None,
    ) -> Dict[str, str]:
        """Build compression metadata dict for MinIO object upload.

        Args:
            original_size: Size of original uncompressed data in bytes.
            compressed_size: Size of compressed data in bytes.
            level: Compression level used. Uses config default if not specified.

        Returns:
            Dictionary with metadata keys for MinIO upload.
        """
        compression_level = level if level is not None else settings.compression_default_level
        return {
            METADATA_COMPRESSION_ALGORITHM: settings.compression_algorithm,
            METADATA_COMPRESSION_LEVEL: str(compression_level),
            METADATA_ORIGINAL_SIZE: str(original_size),
            METADATA_COMPRESSED_SIZE: str(compressed_size),
        }

    def _parse_compression_metadata(self, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Parse compression metadata from MinIO object metadata.

        Args:
            metadata: Object metadata dictionary from MinIO.

        Returns:
            Dictionary with compression info (algorithm, level, original_size, compressed_size).
            Empty dict if no compression metadata found.
        """
        result: Dict[str, Any] = {}

        # MinIO returns metadata keys in lowercase
        meta_lower = {k.lower(): v for k, v in metadata.items()}

        algorithm = meta_lower.get(METADATA_COMPRESSION_ALGORITHM.lower())
        if algorithm:
            result["algorithm"] = algorithm

        level = meta_lower.get(METADATA_COMPRESSION_LEVEL.lower())
        if level:
            result["level"] = int(level)

        original_size = meta_lower.get(METADATA_ORIGINAL_SIZE.lower())
        if original_size:
            result["original_size"] = int(original_size)

        compressed_size = meta_lower.get(METADATA_COMPRESSED_SIZE.lower())
        if compressed_size:
            result["compressed_size"] = int(compressed_size)

        return result

    def download_json(self, bucket: str, object_path: str) -> Dict[str, Any]:
        """Download and parse a JSON object from MinIO with auto-decompression.

        This method downloads the object from MinIO, automatically detects if it's
        compressed via metadata, decompresses if needed, and parses the JSON.
        Maintains backward compatibility with uncompressed files.

        Args:
            bucket: MinIO bucket name.
            object_path: Path to the object within the bucket.

        Returns:
            Parsed JSON data as a dictionary.

        Raises:
            RuntimeError: If the object cannot be fetched, decompressed, or parsed.
        """
        logger.info("Downloading JSON from MinIO bucket=%s, path=%s", bucket, object_path)
        try:
            # First, get object metadata to check compression
            stat = self._client.stat_object(bucket, object_path)
            metadata = stat.metadata or {}

            # Download the object
            response = self._client.get_object(bucket, object_path)
            try:
                raw_data = response.read()
            finally:
                response.close()
                response.release_conn()

            # Check if compressed and decompress if needed
            if self._is_compressed(metadata):
                compression_meta = self._parse_compression_metadata(metadata)
                logger.debug(
                    "Decompressing data: algorithm=%s, compressed_size=%d, original_size=%d",
                    compression_meta.get("algorithm"),
                    compression_meta.get("compressed_size", len(raw_data)),
                    compression_meta.get("original_size", 0),
                )
                try:
                    decompressed_data = self._decompress_data(raw_data)
                except RuntimeError as exc:
                    logger.error("Decompression failed: %s", exc)
                    raise
                json_str = decompressed_data.decode("utf-8")
            else:
                # Uncompressed file - backward compatibility
                json_str = raw_data.decode("utf-8")

            # Parse JSON
            data = json.loads(json_str)
            if not isinstance(data, dict):
                raise RuntimeError("Expected JSON object (dict) from MinIO")
            return data

        except Exception as exc:  # pragma: no cover - I/O heavy path
            logger.error("Failed to fetch JSON from MinIO: %s", exc)
            raise RuntimeError(f"Failed to fetch from MinIO: {exc}") from exc

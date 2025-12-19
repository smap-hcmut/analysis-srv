"""MinIO storage adapter for reading Atomic JSON posts.

This module wraps the MinIO Python SDK behind a small adapter so that
callers (e.g. orchestrated consumers) can fetch JSON objects from MinIO
without depending directly on the SDK.

Supports both Analytics service format and Crawler service format:
- Analytics: Uses compression-algorithm metadata
- Crawler: Uses compressed="true" metadata with JSON arrays
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional, Union

import zstandard as zstd
from minio import Minio  # type: ignore
from minio.error import S3Error  # type: ignore

from core.config import settings
from core.logger import logger
from infrastructure.storage.constants import (
    METADATA_COMPRESSED,
    METADATA_COMPRESSED_SIZE,
    METADATA_COMPRESSION_ALGORITHM,
    METADATA_COMPRESSION_LEVEL,
    METADATA_ORIGINAL_SIZE,
)


class MinioAdapterError(Exception):
    """Base exception for MinIO adapter operations."""

    pass


class MinioObjectNotFoundError(MinioAdapterError):
    """Raised when requested object does not exist."""

    pass


class MinioDecompressionError(MinioAdapterError):
    """Raised when decompression fails."""

    pass


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

        Supports both Analytics and Crawler metadata formats:
        - Analytics: compression-algorithm == "zstd"
        - Crawler: compressed == "true"

        Args:
            metadata: Object metadata dictionary from MinIO.

        Returns:
            True if the object is compressed, False otherwise.
        """
        compression_meta = self._get_compression_metadata(metadata)

        # Check Analytics format: compression-algorithm == "zstd"
        algorithm = compression_meta.get("algorithm")
        if algorithm == "zstd":
            return True

        # Check Crawler format: compressed == "true"
        compressed_flag = compression_meta.get("compressed")
        if compressed_flag and compressed_flag.lower() == "true":
            return True

        return False

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

        Supports both Analytics and Crawler metadata formats.

        Args:
            metadata: Object metadata dictionary from MinIO.

        Returns:
            Dictionary with compression info (algorithm, level, original_size, compressed_size, compressed).
            Empty dict if no compression metadata found.
        """
        result: Dict[str, Any] = {}

        # MinIO returns metadata keys in lowercase
        meta_lower = {k.lower(): v for k, v in metadata.items()}

        # Check for "compressed" flag (Crawler format)
        compressed = meta_lower.get(METADATA_COMPRESSED.lower())
        if compressed:
            result["compressed"] = compressed

        # Check for compression algorithm
        algorithm = meta_lower.get(METADATA_COMPRESSION_ALGORITHM.lower())
        if algorithm:
            result["algorithm"] = algorithm

        # Check for compression level
        level = meta_lower.get(METADATA_COMPRESSION_LEVEL.lower())
        if level:
            try:
                result["level"] = int(level)
            except ValueError:
                pass

        # Check for original size
        original_size = meta_lower.get(METADATA_ORIGINAL_SIZE.lower())
        if original_size:
            try:
                result["original_size"] = int(original_size)
            except ValueError:
                pass

        # Check for compressed size
        compressed_size = meta_lower.get(METADATA_COMPRESSED_SIZE.lower())
        if compressed_size:
            try:
                result["compressed_size"] = int(compressed_size)
            except ValueError:
                pass

        return result

    def download_json(
        self, bucket: str, object_path: str
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Download and parse a JSON object from MinIO with auto-decompression.

        This method downloads the object from MinIO, automatically detects if it's
        compressed via metadata, decompresses if needed, and parses the JSON.
        Maintains backward compatibility with uncompressed files.

        Supports both JSON objects (dict) and JSON arrays (list) to be compatible
        with both Analytics service format and Crawler service format.

        Args:
            bucket: MinIO bucket name.
            object_path: Path to the object within the bucket.

        Returns:
            Parsed JSON data as a dictionary or list of dictionaries.

        Raises:
            MinioObjectNotFoundError: If the object does not exist.
            MinioDecompressionError: If decompression fails.
            MinioAdapterError: If the object cannot be fetched or parsed.
        """
        if not bucket or not object_path:
            raise ValueError("bucket and object_path are required")

        logger.info(f"Downloading JSON from MinIO bucket={bucket}, path={object_path}")
        response = None
        try:
            # First, get object metadata to check compression
            try:
                stat = self._client.stat_object(bucket, object_path)
            except S3Error as exc:
                if exc.code == "NoSuchKey":
                    raise MinioObjectNotFoundError(
                        f"Object not found: {bucket}/{object_path}"
                    ) from exc
                raise

            metadata = stat.metadata or {}

            # Download the object
            response = self._client.get_object(bucket, object_path)
            raw_data = response.read()

            # Check if compressed and decompress if needed
            if self._is_compressed(metadata):
                compression_meta = self._parse_compression_metadata(metadata)
                logger.debug(
                    "Decompressing data: algorithm=%s, compressed_size=%d, original_size=%d",
                    compression_meta.get("algorithm", "zstd"),
                    compression_meta.get("compressed_size", len(raw_data)),
                    compression_meta.get("original_size", 0),
                )
                try:
                    decompressed_data = self._decompress_data(raw_data)
                except RuntimeError as exc:
                    raise MinioDecompressionError(str(exc)) from exc
                json_str = decompressed_data.decode("utf-8")
            else:
                # Uncompressed file - backward compatibility
                json_str = raw_data.decode("utf-8")

            # Parse JSON
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as exc:
                raise MinioAdapterError(
                    f"Invalid JSON in object {bucket}/{object_path}: {exc}"
                ) from exc

            # Accept both dict and list (for Crawler compatibility)
            if not isinstance(data, (dict, list)):
                raise MinioAdapterError(
                    f"Expected JSON object (dict) or array (list) from MinIO, got {type(data).__name__}"
                )
            return data

        except (MinioObjectNotFoundError, MinioDecompressionError, MinioAdapterError):
            raise
        except S3Error as exc:
            logger.error(f"MinIO S3 error: {exc}")
            raise MinioAdapterError(f"MinIO S3 error: {exc}") from exc
        except Exception as exc:
            logger.error(f"Failed to fetch JSON from MinIO: {exc}")
            raise MinioAdapterError(f"Failed to fetch from MinIO: {exc}") from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def download_batch(self, bucket: str, object_path: str) -> List[Dict[str, Any]]:
        """Download a batch of items from MinIO.

        This is a convenience method for downloading crawler batches.
        It handles both JSON arrays (Crawler format) and JSON objects with items key.

        Args:
            bucket: MinIO bucket name.
            object_path: Path to the batch file.

        Returns:
            List of batch items.

        Raises:
            MinioObjectNotFoundError: If the object does not exist.
            MinioDecompressionError: If decompression fails.
            MinioAdapterError: If the object cannot be fetched or parsed.
        """
        data = self.download_json(bucket, object_path)

        # Handle different formats
        if isinstance(data, list):
            # Crawler format: direct array
            return data
        elif isinstance(data, dict):
            # Analytics format: object with items key
            if "items" in data:
                return data["items"]
            # Single item wrapped in object
            return [data]
        else:
            raise MinioAdapterError(f"Unexpected batch format: {type(data).__name__}")

    def upload_json(
        self,
        bucket: str,
        object_path: str,
        data: Dict[str, Any],
        *,
        compress: bool = True,
        compression_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upload a JSON object to MinIO with optional compression.

        Args:
            bucket: MinIO bucket name.
            object_path: Path to store the object.
            data: Dictionary to serialize and upload.
            compress: Whether to compress the data (default: True).
            compression_level: Compression level (0-22). Uses config default if not specified.

        Returns:
            Dictionary with upload metadata (size, compressed_size, etc.).

        Raises:
            MinioAdapterError: If upload fails.
        """
        if not bucket or not object_path:
            raise ValueError("bucket and object_path are required")

        try:
            json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            original_size = len(json_bytes)

            metadata: Dict[str, str] = {"Content-Type": "application/json"}

            if compress and original_size >= settings.compression_min_size_bytes:
                compressed_bytes = self._compress_data(json_bytes, compression_level)
                compressed_size = len(compressed_bytes)

                # Only use compression if it actually reduces size
                if compressed_size < original_size:
                    metadata.update(
                        self._build_compression_metadata(
                            original_size, compressed_size, compression_level
                        )
                    )
                    upload_data = compressed_bytes
                    final_size = compressed_size
                else:
                    upload_data = json_bytes
                    final_size = original_size
            else:
                upload_data = json_bytes
                final_size = original_size

            self._client.put_object(
                bucket,
                object_path,
                io.BytesIO(upload_data),
                length=len(upload_data),
                metadata=metadata,
            )

            logger.info(
                f"Uploaded JSON to MinIO bucket={bucket}, path={object_path}, size={final_size}"
            )

            return {
                "bucket": bucket,
                "path": object_path,
                "original_size": original_size,
                "final_size": final_size,
                "compressed": final_size < original_size,
            }

        except S3Error as exc:
            logger.error(f"MinIO S3 error during upload: {exc}")
            raise MinioAdapterError(f"MinIO upload failed: {exc}") from exc
        except Exception as exc:
            logger.error(f"Failed to upload JSON to MinIO: {exc}")
            raise MinioAdapterError(f"Upload failed: {exc}") from exc

from __future__ import annotations

import io
import json
from typing import Dict, List, Optional, Union

import zstandard as zstd  # type: ignore
from minio import Minio  # type: ignore
from minio.error import S3Error  # type: ignore

from loguru import logger
from .interface import IObjectStorage
from .type import MinIOConfig, CompressionConfig, UploadResult
from .constant import *


class MinioAdapterError(Exception):
    """Base exception for MinIO adapter operations."""

    pass


class MinioObjectNotFoundError(MinioAdapterError):
    """Raised when requested object does not exist."""

    pass


class MinioDecompressionError(MinioAdapterError):
    """Raised when decompression fails."""

    pass


class MinioAdapter(IObjectStorage):
    """Thin wrapper around MinIO client to download JSON objects.

    Attributes:
        config: MinIO configuration
        compression_config: Compression configuration
    """

    def __init__(
        self,
        config: MinIOConfig,
        compression_config: Optional[CompressionConfig] = None,
    ):
        """Initialize MinIO adapter with configuration.

        Args:
            config: MinIO configuration
            compression_config: Optional compression configuration

        Raises:
            ImportError: If minio or zstandard is not installed
        """
        self.config = config
        self.compression_config = compression_config or CompressionConfig()

        # Create MinIO client
        self._client = Minio(
            self.config.endpoint,
            access_key=self.config.access_key,
            secret_key=self.config.secret_key,
            secure=self.config.secure,
            region=self.config.region,
        )

        # Create compressor/decompressor
        self._compressor = zstd.ZstdCompressor(level=self.compression_config.level)
        self._decompressor = zstd.ZstdDecompressor()

    def _compress_data(self, data: bytes, level: Optional[int] = None) -> bytes:
        """Compress data using Zstd algorithm.

        Args:
            data: Raw bytes to compress.
            level: Compression level (0-22). Uses config default if not specified.

        Returns:
            Compressed bytes.
        """
        if level is not None and level != self.compression_config.level:
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

    def _get_compression_metadata(
        self, metadata: Dict[str, str]
    ) -> Dict[str, Union[str, int]]:
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
        compression_level = (
            level if level is not None else self.compression_config.level
        )
        return {
            METADATA_COMPRESSION_ALGORITHM: self.compression_config.algorithm,
            METADATA_COMPRESSION_LEVEL: str(compression_level),
            METADATA_ORIGINAL_SIZE: str(original_size),
            METADATA_COMPRESSED_SIZE: str(compressed_size),
        }

    def _parse_compression_metadata(
        self, metadata: Dict[str, str]
    ) -> Dict[str, Union[str, int]]:
        """Parse compression metadata from MinIO object metadata.

        Supports both Analytics and Crawler metadata formats.

        Args:
            metadata: Object metadata dictionary from MinIO.

        Returns:
            Dictionary with compression info (algorithm, level, original_size, compressed_size, compressed).
            Empty dict if no compression metadata found.
        """
        result: Dict[str, Union[str, int]] = {}

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
    ) -> Union[Dict[str, object], List[Dict[str, object]]]:
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

    def download_batch(self, bucket: str, object_path: str) -> List[Dict[str, object]]:
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
        data: Dict[str, object],
        *,
        compress: bool = True,
        compression_level: Optional[int] = None,
    ) -> UploadResult:
        """Upload a JSON object to MinIO with optional compression.

        Args:
            bucket: MinIO bucket name.
            object_path: Path to store the object.
            data: Dictionary to serialize and upload.
            compress: Whether to compress the data (default: True).
            compression_level: Compression level (0-22). Uses config default if not specified.

        Returns:
            UploadResult with upload metadata.

        Raises:
            MinioAdapterError: If upload fails.
        """
        if not bucket or not object_path:
            raise ValueError("bucket and object_path are required")

        try:
            json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            original_size = len(json_bytes)

            metadata: Dict[str, str] = {"Content-Type": "application/json"}
            was_compressed = False

            if (
                compress
                and self.compression_config.enabled
                and original_size >= self.compression_config.min_size_bytes
            ):
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
                    was_compressed = True
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

            return UploadResult(
                bucket=bucket,
                path=object_path,
                original_size=original_size,
                final_size=final_size,
                compressed=was_compressed,
                metadata=metadata,
            )

        except S3Error as exc:
            logger.error(f"MinIO S3 error during upload: {exc}")
            raise MinioAdapterError(f"MinIO upload failed: {exc}") from exc
        except Exception as exc:
            logger.error(f"Failed to upload JSON to MinIO: {exc}")
            raise MinioAdapterError(f"Upload failed: {exc}") from exc

    def object_exists(self, bucket: str, object_path: str) -> bool:
        """Check if object exists in MinIO.

        Args:
            bucket: MinIO bucket name
            object_path: Path to the object

        Returns:
            True if object exists, False otherwise
        """
        try:
            self._client.stat_object(bucket, object_path)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise MinioAdapterError(f"Failed to check object existence: {exc}") from exc


__all__ = [
    "MinioAdapter",
    "MinioAdapterError",
    "MinioObjectNotFoundError",
    "MinioDecompressionError",
]

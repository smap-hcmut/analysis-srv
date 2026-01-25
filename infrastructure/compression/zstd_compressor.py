"""
Zstandard (Zstd) compression implementation.

Provides high-performance compression with excellent ratios,
particularly effective for JSON and text data (60-95% reduction).
"""

import zstandard as zstd
from typing import BinaryIO
import logging

from .interfaces import ICompressor, CompressionInfo


logger = logging.getLogger(__name__)


class ZstdCompressor(ICompressor):
    """
    Zstandard compression implementation.

    Zstd provides excellent compression ratios with fast compression/decompression.
    Ideal for JSON data, achieving 60-95% size reduction.

    Compression Levels:
        0: No compression (passthrough)
        1: Fast compression (lowest CPU, ~50-70% reduction)
        2: Default compression (balanced, ~70-85% reduction)
        3: Best compression (highest CPU, ~85-95% reduction)
    """

    # Map our simple levels to zstd compression levels
    LEVEL_MAP = {
        0: 0,  # No compression
        1: 3,  # Fast (zstd level 3)
        2: 10,  # Default (zstd level 10)
        3: 19,  # Best (zstd level 19, max is 22)
    }

    def __init__(self):
        """Initialize Zstd compressor with default settings."""
        self.algorithm_name = "zstd"

    def compress(self, data: bytes, level: int = 2) -> bytes:
        """
        Compress bytes data using Zstd.

        Args:
            data: Raw bytes to compress
            level: Compression level (0-3)

        Returns:
            Compressed bytes

        Raises:
            ValueError: If level is invalid
            zstd.ZstdError: If compression fails
        """
        if level not in self.LEVEL_MAP:
            raise ValueError(f"Invalid compression level: {level}. Must be 0-3.")

        # Level 0 = no compression, return as-is
        if level == 0:
            return data

        zstd_level = self.LEVEL_MAP[level]

        try:
            compressor = zstd.ZstdCompressor(level=zstd_level)
            compressed = compressor.compress(data)

            logger.debug(
                f"Compressed {len(data)} bytes to {len(compressed)} bytes "
                f"(level={level}, ratio={len(compressed)/len(data)*100:.2f}%)"
            )

            return compressed

        except zstd.ZstdError as e:
            logger.error(f"Zstd compression failed: {e}")
            raise

    def decompress(self, data: bytes) -> bytes:
        """
        Decompress Zstd-compressed bytes.

        Args:
            data: Compressed bytes

        Returns:
            Decompressed bytes

        Raises:
            zstd.ZstdError: If decompression fails
        """
        try:
            decompressor = zstd.ZstdDecompressor()
            decompressed = decompressor.decompress(data)

            logger.debug(f"Decompressed {len(data)} bytes to {len(decompressed)} bytes")

            return decompressed

        except zstd.ZstdError as e:
            logger.error(f"Zstd decompression failed: {e}")
            raise

    def compress_stream(
        self, source: BinaryIO, destination: BinaryIO, level: int = 2, chunk_size: int = 8192
    ) -> CompressionInfo:
        """
        Compress data from source stream to destination stream.

        Useful for large files that don't fit in memory.

        Args:
            source: Input stream (readable binary)
            destination: Output stream (writable binary)
            level: Compression level (0-3)
            chunk_size: Size of chunks to read/write

        Returns:
            CompressionInfo with compression statistics

        Raises:
            ValueError: If level is invalid
            zstd.ZstdError: If compression fails
        """
        if level not in self.LEVEL_MAP:
            raise ValueError(f"Invalid compression level: {level}. Must be 0-3.")

        original_size = 0
        compressed_size = 0

        try:
            # Level 0 = no compression, copy data
            if level == 0:
                while True:
                    chunk = source.read(chunk_size)
                    if not chunk:
                        break
                    original_size += len(chunk)
                    destination.write(chunk)
                    compressed_size += len(chunk)

                return self.get_compression_info(original_size, compressed_size, level)

            zstd_level = self.LEVEL_MAP[level]
            compressor = zstd.ZstdCompressor(level=zstd_level)

            # Stream compression
            with compressor.stream_writer(destination, closefd=False) as writer:
                while True:
                    chunk = source.read(chunk_size)
                    if not chunk:
                        break
                    original_size += len(chunk)
                    writer.write(chunk)

            # Get compressed size (position in destination stream)
            compressed_size = destination.tell()

            logger.info(
                f"Stream compressed {original_size} bytes to {compressed_size} bytes "
                f"(level={level}, ratio={compressed_size/original_size*100:.2f}%)"
            )

            return self.get_compression_info(original_size, compressed_size, level)

        except zstd.ZstdError as e:
            logger.error(f"Zstd stream compression failed: {e}")
            raise

    def decompress_stream(
        self, source: BinaryIO, destination: BinaryIO, chunk_size: int = 8192
    ) -> int:
        """
        Decompress data from source stream to destination stream.

        Args:
            source: Input stream (readable binary, compressed)
            destination: Output stream (writable binary)
            chunk_size: Size of chunks to process

        Returns:
            Total bytes decompressed

        Raises:
            zstd.ZstdError: If decompression fails
        """
        try:
            decompressor = zstd.ZstdDecompressor()
            total_decompressed = 0

            # Stream decompression
            with decompressor.stream_reader(source, closefd=False) as reader:
                while True:
                    chunk = reader.read(chunk_size)
                    if not chunk:
                        break
                    destination.write(chunk)
                    total_decompressed += len(chunk)

            logger.info(f"Stream decompressed {total_decompressed} bytes")

            return total_decompressed

        except zstd.ZstdError as e:
            logger.error(f"Zstd stream decompression failed: {e}")
            raise

    def get_algorithm_name(self) -> str:
        """
        Get the algorithm name.

        Returns:
            "zstd"
        """
        return self.algorithm_name

    @staticmethod
    def is_available() -> bool:
        """
        Check if zstandard library is available.

        Returns:
            True if zstandard is installed
        """
        try:
            import zstandard

            return True
        except ImportError:
            return False

    @staticmethod
    def get_version() -> str:
        """
        Get zstandard library version.

        Returns:
            Version string or "unknown" if not available
        """
        try:
            return zstd.ZSTD_VERSION_STRING
        except AttributeError:
            return "unknown"

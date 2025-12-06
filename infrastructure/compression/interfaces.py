"""
Compression interfaces and data models.

Defines abstract interfaces for compression implementations,
allowing easy swapping of compression algorithms (Zstd, Gzip, Brotli, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Optional


@dataclass
class CompressionInfo:
    """Information about compression operation results."""

    original_size: int
    compressed_size: int
    compression_ratio: float
    algorithm: str
    level: int

    @staticmethod
    def calculate_ratio(original_size: int, compressed_size: int) -> float:
        """
        Calculate compression ratio (compressed / original).

        Returns:
            Ratio between 0.0 and 1.0 (lower is better compression)
        """
        if original_size == 0:
            return 0.0
        return compressed_size / original_size

    def get_savings_percentage(self) -> float:
        """
        Get percentage of space saved by compression.

        Returns:
            Percentage saved (e.g., 94.5 means 94.5% reduction)
        """
        return (1 - self.compression_ratio) * 100


class ICompressor(ABC):
    """
    Abstract interface for compression implementations.

    Implementations should support both in-memory compression
    for small data and streaming compression for large files.
    """

    @abstractmethod
    def compress(self, data: bytes, level: int = 2) -> bytes:
        """
        Compress bytes data in memory.

        Args:
            data: Raw bytes to compress
            level: Compression level (0=none, 1=fast, 2=default, 3=best)

        Returns:
            Compressed bytes
        """
        pass

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        """
        Decompress bytes data in memory.

        Args:
            data: Compressed bytes

        Returns:
            Decompressed bytes
        """
        pass

    @abstractmethod
    def compress_stream(
        self, source: BinaryIO, destination: BinaryIO, level: int = 2, chunk_size: int = 8192
    ) -> CompressionInfo:
        """
        Compress data from source stream to destination stream.

        Useful for large files that don't fit in memory.

        Args:
            source: Input stream (readable binary)
            destination: Output stream (writable binary)
            level: Compression level
            chunk_size: Size of chunks to process at a time

        Returns:
            Compression information (sizes, ratio)
        """
        pass

    @abstractmethod
    def decompress_stream(
        self, source: BinaryIO, destination: BinaryIO, chunk_size: int = 8192
    ) -> int:
        """
        Decompress data from source stream to destination stream.

        Args:
            source: Input stream (readable binary)
            destination: Output stream (writable binary)
            chunk_size: Size of chunks to process at a time

        Returns:
            Total bytes decompressed
        """
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """
        Get the name of the compression algorithm.

        Returns:
            Algorithm name (e.g., "zstd", "gzip", "brotli")
        """
        pass

    def get_compression_info(
        self, original_size: int, compressed_size: int, level: int
    ) -> CompressionInfo:
        """
        Create CompressionInfo object with algorithm details.

        Args:
            original_size: Size of original data
            compressed_size: Size of compressed data
            level: Compression level used

        Returns:
            CompressionInfo object
        """
        ratio = CompressionInfo.calculate_ratio(original_size, compressed_size)
        return CompressionInfo(
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=ratio,
            algorithm=self.get_algorithm_name(),
            level=level,
        )

"""Interface for Zstd compression operations."""

from typing import BinaryIO, Protocol, runtime_checkable

from .type import ZstdCompressionInfo
from .constant import DEFAULT_LEVEL, DEFAULT_CHUNK_SIZE


@runtime_checkable
class IZstd(Protocol):
    """Protocol for compression operations."""

    def compress(self, data: bytes, level: int = DEFAULT_LEVEL) -> bytes:
        """Compress bytes data in memory."""
        ...

    def decompress(self, data: bytes) -> bytes:
        """Decompress bytes data in memory."""
        ...

    def compress_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        level: int = DEFAULT_LEVEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> ZstdCompressionInfo:
        """Compress data from source stream to destination stream."""
        ...

    def decompress_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> int:
        """Decompress data from source stream to destination stream."""
        ...


__all__ = ["IZstd"]

from typing import BinaryIO, Protocol, runtime_checkable
import zstandard as zstd  # type: ignore

from .constant import *
from .type import ZstdConfig, ZstdCompressionInfo


@runtime_checkable
class IZstd(Protocol):
    """
    Protocol defining the compression interface.
    """

    def compress(self, data: bytes, level: int = DEFAULT_LEVEL) -> bytes:
        """
        Compress bytes data in memory.

        Args:
            data: Raw bytes to compress
            level: Compression level (0=none, 1=fast, 2=default, 3=best)

        Returns:
            Compressed bytes
        """
        ...

    def decompress(self, data: bytes) -> bytes:
        """
        Decompress bytes data in memory.

        Args:
            data: Compressed bytes

        Returns:
            Decompressed bytes
        """
        ...

    def compress_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        level: int = DEFAULT_LEVEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> ZstdCompressionInfo:
        """
        Compress data from source stream to destination stream.

        Args:
            source: Input stream (readable binary)
            destination: Output stream (writable binary)
            level: Compression level
            chunk_size: Size of chunks to process at a time

        Returns:
            Compression information (sizes, ratio)
        """
        ...

    def decompress_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
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
        ...


class Zstd(IZstd):
    """
    Zstandard compression implementation.

    Zstd provides excellent compression ratios with fast compression/decompression.
    """

    def __init__(self, config: ZstdConfig):
        """Initialize Zstd compressor with configuration.

        Args:
            config: ZstdConfig configuration

        Raises:
            ImportError: If zstandard library is not installed
        """
        self.config = config

        if zstd is None:
            raise ImportError(ERROR_LIB_NOT_INSTALLED)

    def compress(self, data: bytes, level: int = DEFAULT_LEVEL) -> bytes:
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
        if level not in ZSTD_LEVEL_MAP:
            raise ValueError(ERROR_INVALID_LEVEL.format(level=level))

        # Level 0 = no compression, return as-is
        if level == LEVEL_NO_COMPRESSION:
            return data

        zstd_level = ZSTD_LEVEL_MAP[level]

        try:
            compressor = zstd.ZstdCompressor(level=zstd_level)
            return compressor.compress(data)
        except zstd.ZstdError as e:
            raise zstd.ZstdError(ERROR_COMPRESSION_FAILED.format(error=e)) from e

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
            return decompressor.decompress(data)
        except zstd.ZstdError as e:
            raise zstd.ZstdError(ERROR_DECOMPRESSION_FAILED.format(error=e)) from e

    def compress_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        level: int = DEFAULT_LEVEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> ZstdCompressionInfo:
        """
        Compress data from source stream to destination stream.

        Args:
            source: Input stream (readable binary)
            destination: Output stream (writable binary)
            level: Compression level (0-3), defaults to config.default_level
            chunk_size: Size of chunks to read/write, defaults to config.chunk_size

        Returns:
            ZstdCompressionInfo with compression statistics

        Raises:
            ValueError: If level is invalid
            zstd.ZstdError: If compression fails
        """
        if level not in ZSTD_LEVEL_MAP:
            raise ValueError(ERROR_INVALID_LEVEL.format(level=level))

        original_size = 0
        compressed_size = 0

        try:
            # Level 0 = no compression, copy data
            if level == LEVEL_NO_COMPRESSION:
                while True:
                    chunk = source.read(chunk_size)
                    if not chunk:
                        break
                    original_size += len(chunk)
                    destination.write(chunk)
                    compressed_size += len(chunk)

                return ZstdCompressionInfo(
                    original_size=original_size,
                    compressed_size=compressed_size,
                    compression_ratio=ZstdCompressionInfo.calculate_ratio(
                        original_size, compressed_size
                    ),
                    algorithm=ALGORITHM_NAME,
                    level=level,
                )

            zstd_level = ZSTD_LEVEL_MAP[level]
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

            return ZstdCompressionInfo(
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=ZstdCompressionInfo.calculate_ratio(
                    original_size, compressed_size
                ),
                algorithm=ALGORITHM_NAME,
                level=level,
            )

        except zstd.ZstdError as e:
            raise zstd.ZstdError(ERROR_STREAM_COMPRESSION_FAILED.format(error=e)) from e

    def decompress_stream(
        self,
        source: BinaryIO,
        destination: BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> int:
        """
        Decompress data from source stream to destination stream.

        Args:
            source: Input stream (readable binary, compressed)
            destination: Output stream (writable binary)
            chunk_size: Size of chunks to process, defaults to config.chunk_size

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

            return total_decompressed

        except zstd.ZstdError as e:
            raise zstd.ZstdError(
                ERROR_STREAM_DECOMPRESSION_FAILED.format(error=e)
            ) from e


__all__ = [
    "Zstd",
    "IZstd",
    "ZstdConfig",
    "ZstdCompressionInfo",
]

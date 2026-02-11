from dataclasses import dataclass
from .constant import *


@dataclass
class ZstdConfig:
    """Zstd compressor configuration.

    Attributes:
        default_level: Default compression level (0-3)
        chunk_size: Default chunk size for streaming (bytes)
    """

    default_level: int = DEFAULT_LEVEL
    chunk_size: int = DEFAULT_CHUNK_SIZE

    def __post_init__(self):
        """Validate configuration."""
        if not 0 <= self.default_level <= 3:
            raise ValueError(ERROR_INVALID_LEVEL.format(level=self.default_level))

        if self.chunk_size <= 0:
            raise ValueError(ERROR_CHUNK_SIZE_POSITIVE.format(size=self.chunk_size))


@dataclass
class ZstdCompressionInfo:
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

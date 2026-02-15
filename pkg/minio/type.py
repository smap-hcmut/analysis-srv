from dataclasses import dataclass
from typing import Dict, Optional
from .constant import *


@dataclass
class MinIOConfig:
    """MinIO client configuration.

    Attributes:
        endpoint: MinIO server endpoint (e.g., 'localhost:9000')
        access_key: Access key for authentication
        secret_key: Secret key for authentication
        secure: Whether to use HTTPS
        region: Optional region name
    """

    endpoint: str
    access_key: str
    secret_key: str
    secure: bool = False
    region: Optional[str] = None

    def __post_init__(self):
        """Validate configuration."""
        if not self.endpoint or not self.endpoint.strip():
            raise ValueError("endpoint cannot be empty")

        if not self.access_key or not self.access_key.strip():
            raise ValueError("access_key cannot be empty")

        if not self.secret_key or not self.secret_key.strip():
            raise ValueError("secret_key cannot be empty")

        self.endpoint = (
            self.endpoint.replace("http://", "").replace("https://", "").strip()
        )


@dataclass
class CompressionConfig:
    """Compression configuration for storage operations.

    Attributes:
        enabled: Whether compression is enabled
        algorithm: Compression algorithm ('zstd')
        level: Compression level (0-22 for zstd)
        min_size_bytes: Minimum size to compress (bytes)
    """

    enabled: bool = True
    algorithm: str = "zstd"
    level: int = 10
    min_size_bytes: int = 1024

    def __post_init__(self):
        """Validate configuration."""
        if self.algorithm not in ["zstd"]:
            raise ValueError(f"algorithm must be 'zstd', got {self.algorithm}")

        if not 0 <= self.level <= 22:
            raise ValueError(f"level must be 0-22, got {self.level}")

        if self.min_size_bytes < 0:
            raise ValueError(
                f"min_size_bytes must be non-negative, got {self.min_size_bytes}"
            )


@dataclass
class UploadResult:
    """Result of upload operation.

    Attributes:
        bucket: Bucket name
        path: Object path
        original_size: Original data size in bytes
        final_size: Final uploaded size in bytes
        compressed: Whether data was compressed
        metadata: Additional metadata
    """

    bucket: str
    path: str
    original_size: int
    final_size: int
    compressed: bool
    metadata: Dict[str, str]

    def get_compression_ratio(self) -> float:
        """Calculate compression ratio.

        Returns:
            Ratio (0.0-1.0), lower is better compression
        """
        if self.original_size == 0:
            return 0.0
        return self.final_size / self.original_size

    def get_savings_percentage(self) -> float:
        """Calculate space savings percentage.

        Returns:
            Percentage saved (0-100)
        """
        return (1 - self.get_compression_ratio()) * 100


__all__ = [
    "MinIOConfig",
    "CompressionConfig",
    "UploadResult",
]

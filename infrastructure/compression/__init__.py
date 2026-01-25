"""
Compression infrastructure for MinIO storage.

Provides compression/decompression capabilities for data before upload
to MinIO object storage, reducing storage costs and bandwidth usage.
"""

from .interfaces import ICompressor, CompressionInfo
from .zstd_compressor import ZstdCompressor

__all__ = [
    "ICompressor",
    "CompressionInfo",
    "ZstdCompressor",
]

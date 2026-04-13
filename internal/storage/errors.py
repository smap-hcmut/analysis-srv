"""storage/errors.py — storage-layer exceptions."""

from __future__ import annotations


class StorageError(Exception):
    """Base class for storage errors."""


class ParquetWriteError(StorageError):
    """Raised when writing a Parquet file fails."""


class JsonlWriteError(StorageError):
    """Raised when writing a JSONL file fails."""


class DuckDBRegistrationError(StorageError):
    """Raised when registering Parquet tables in DuckDB fails."""


__all__ = [
    "StorageError",
    "ParquetWriteError",
    "JsonlWriteError",
    "DuckDBRegistrationError",
]

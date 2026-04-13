"""storage/interface.py — IStorageRepository ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import polars as pl
    from pydantic import BaseModel


class IStorageRepository(ABC):
    """Minimal storage repository contract used by pipeline stages."""

    @abstractmethod
    def write_parquet(self, path: Path, records: "list[dict]") -> "pl.DataFrame":
        """Write a list of dicts to a Parquet file; return the resulting DataFrame."""

    @abstractmethod
    def write_models_parquet(
        self, path: Path, records: "Iterable[BaseModel]"
    ) -> "pl.DataFrame":
        """Serialise Pydantic models to dicts and write as Parquet."""

    @abstractmethod
    def write_jsonl(self, path: Path, records: "Iterable[dict]") -> None:
        """Write records as newline-delimited JSON."""

    @abstractmethod
    def write_table_bundle(
        self, output_dir: Path, tables: "dict[str, pl.DataFrame]"
    ) -> "dict[str, Path]":
        """Write a name→DataFrame mapping to individual Parquet files."""

    @abstractmethod
    def register_tables(
        self, duckdb_path: Path, table_paths: "dict[str, Path]"
    ) -> None:
        """Register Parquet files as tables in a DuckDB database file."""


__all__ = ["IStorageRepository"]

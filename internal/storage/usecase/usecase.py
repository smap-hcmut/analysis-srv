"""storage/usecase/usecase.py — StorageRepository: concrete IStorageRepository."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl
from pydantic import BaseModel

from internal.storage.interface import IStorageRepository
from internal.storage.usecase.register_tables import register_parquet_tables
from internal.storage.usecase.write_jsonl import write_jsonl
from internal.storage.usecase.write_parquet import (
    write_dicts_parquet,
    write_models_parquet,
)
from internal.storage.usecase.write_table_bundle import write_table_bundle


class StorageRepository(IStorageRepository):
    """Default implementation — writes to local filesystem."""

    def write_parquet(self, path: Path, records: list[dict]) -> pl.DataFrame:
        return write_dicts_parquet(path, records)

    def write_models_parquet(
        self, path: Path, records: Iterable[BaseModel]
    ) -> pl.DataFrame:
        return write_models_parquet(path, records)

    def write_jsonl(self, path: Path, records: Iterable[dict]) -> None:
        write_jsonl(path, records)

    def write_table_bundle(
        self, output_dir: Path, tables: dict[str, pl.DataFrame]
    ) -> dict[str, Path]:
        return write_table_bundle(output_dir, tables)

    def register_tables(self, duckdb_path: Path, table_paths: dict[str, Path]) -> None:
        register_parquet_tables(duckdb_path, table_paths)


__all__ = ["StorageRepository"]

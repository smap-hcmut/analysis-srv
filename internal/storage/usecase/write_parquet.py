"""storage/usecase/write_parquet.py — write dict/model lists to Parquet."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl
from pydantic import BaseModel

from internal.storage.errors import ParquetWriteError


def write_dicts_parquet(path: Path, records: list[dict]) -> pl.DataFrame:
    """Write a list of dicts to *path* as Parquet; return the resulting DataFrame.

    An empty list produces an empty DataFrame (no columns) written to disk.
    Raises :class:`ParquetWriteError` on I/O failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame = (
            pl.DataFrame(records, infer_schema_length=len(records))
            if records
            else pl.DataFrame([])
        )
        frame.write_parquet(path)
        return frame
    except Exception as exc:
        raise ParquetWriteError(f"Failed to write Parquet to {path}: {exc}") from exc


def write_models_parquet(path: Path, records: Iterable[BaseModel]) -> pl.DataFrame:
    """Serialize Pydantic models → dicts → Parquet.

    Equivalent to calling :func:`write_dicts_parquet` after
    ``model.model_dump(mode='json')`` for each record.
    """
    materialized = [r.model_dump(mode="json") for r in records]
    return write_dicts_parquet(path, materialized)


__all__ = ["write_dicts_parquet", "write_models_parquet"]

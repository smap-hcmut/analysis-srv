"""storage/usecase/write_table_bundle.py — write a name→DataFrame mapping to Parquet files."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from internal.storage.errors import ParquetWriteError


def write_table_bundle(
    output_dir: Path, tables: dict[str, pl.DataFrame]
) -> dict[str, Path]:
    """Write each DataFrame in *tables* to ``output_dir/<name>.parquet``.

    Returns a mapping of table name → written path.
    Raises :class:`ParquetWriteError` on I/O failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    table_paths: dict[str, Path] = {}
    for table_name, frame in tables.items():
        path = output_dir / f"{table_name}.parquet"
        try:
            frame.write_parquet(path)
        except Exception as exc:
            raise ParquetWriteError(
                f"Failed to write table '{table_name}' to {path}: {exc}"
            ) from exc
        table_paths[table_name] = path
    return table_paths


__all__ = ["write_table_bundle"]

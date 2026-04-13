"""storage/usecase/register_tables.py — register Parquet files as DuckDB tables."""

from __future__ import annotations

from pathlib import Path

from internal.storage.errors import DuckDBRegistrationError


def register_parquet_tables(duckdb_path: Path, table_paths: dict[str, Path]) -> None:
    """Open (or create) a DuckDB database at *duckdb_path* and register each
    Parquet file in *table_paths* as a persistent table via ``CREATE OR REPLACE TABLE``.

    Raises :class:`DuckDBRegistrationError` on failure.
    """
    try:
        import duckdb  # optional dependency
    except ImportError as exc:
        raise DuckDBRegistrationError(
            "duckdb is not installed. Add 'duckdb' to pyproject.toml dependencies."
        ) from exc

    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = duckdb.connect(str(duckdb_path))
        try:
            for table_name, table_path in table_paths.items():
                connection.execute(
                    f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet(?)",
                    [str(table_path)],
                )
        finally:
            connection.close()
    except Exception as exc:
        raise DuckDBRegistrationError(
            f"Failed to register tables in DuckDB at {duckdb_path}: {exc}"
        ) from exc


__all__ = ["register_parquet_tables"]

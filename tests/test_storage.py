"""test_storage.py — Phase 7: internal/storage module tests.

Gate criteria:
- StorageLayout.for_run() creates correct paths under base_dir/run_id/layer
- StorageLayout.ensure_directories() creates all 6 layer directories
- write_dicts_parquet writes a Parquet file readable by Polars
- write_dicts_parquet on empty list produces an empty (0-row) DataFrame
- write_models_parquet serialises Pydantic models correctly
- write_jsonl writes valid JSONL readable back as dicts
- write_text_if_changed returns True on first write, False if unchanged
- write_table_bundle writes multiple named Parquet files and returns correct paths
- StorageRepository implements IStorageRepository
- new_storage_repository() returns a StorageRepository instance
- All 138 previously-passing tests are unaffected
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import polars as pl
import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SampleModel(BaseModel):
    id: str
    value: float


def _tmp_dir() -> Path:
    return Path(tempfile.mkdtemp())


# ---------------------------------------------------------------------------
# StorageLayout
# ---------------------------------------------------------------------------


def test_storage_layout_for_run_default_base():
    """for_run() with no base_dir uses system tmp/analysis-srv."""
    from internal.storage.type import StorageLayout

    layout = StorageLayout.for_run("run-test-001")
    assert layout.run_id == "run-test-001"
    assert "analysis-srv" in str(layout.base_dir)


def test_storage_layout_paths_rooted_under_base():
    """All layer paths must be rooted under base_dir/run_id/."""
    from internal.storage.type import StorageLayout

    base = _tmp_dir()
    layout = StorageLayout.for_run("run-abc", base_dir=base)

    assert layout.bronze_dir == base / "run-abc" / "bronze"
    assert layout.silver_dir == base / "run-abc" / "silver"
    assert layout.gold_dir == base / "run-abc" / "gold"
    assert layout.marts_dir == base / "run-abc" / "gold" / "marts"
    assert layout.reports_dir == base / "run-abc" / "reports"
    assert layout.insights_dir == base / "run-abc" / "insights"


def test_storage_layout_file_paths():
    """Bronze/silver/gold/reports file paths must use correct filenames."""
    from internal.storage.type import StorageLayout

    base = _tmp_dir()
    layout = StorageLayout.for_run("run-file-paths", base_dir=base)

    assert layout.bronze_raw_jsonl.name == "uap_records.jsonl"
    assert layout.silver_mentions.name == "mentions.parquet"
    assert layout.gold_entities.name == "entity_facts.parquet"
    assert layout.bi_reports_file.name == "bi_reports.json"
    assert layout.run_manifest_file.name == "run_manifest.json"
    assert layout.insights_file.name == "insights.jsonl"


def test_storage_layout_ensure_directories():
    """ensure_directories() must create all 6 layer directories."""
    from internal.storage.type import StorageLayout

    base = _tmp_dir()
    layout = StorageLayout.for_run("run-dirs", base_dir=base)
    layout.ensure_directories()

    assert layout.bronze_dir.is_dir()
    assert layout.silver_dir.is_dir()
    assert layout.gold_dir.is_dir()
    assert layout.marts_dir.is_dir()
    assert layout.reports_dir.is_dir()
    assert layout.insights_dir.is_dir()


def test_storage_layout_ensure_directories_idempotent():
    """Calling ensure_directories() twice must not raise."""
    from internal.storage.type import StorageLayout

    base = _tmp_dir()
    layout = StorageLayout.for_run("run-idem", base_dir=base)
    layout.ensure_directories()
    layout.ensure_directories()  # must not raise


# ---------------------------------------------------------------------------
# write_dicts_parquet / write_models_parquet
# ---------------------------------------------------------------------------


def test_write_dicts_parquet_basic(tmp_path):
    """write_dicts_parquet writes a Parquet file with the expected rows."""
    from internal.storage.usecase.write_parquet import write_dicts_parquet

    records = [{"id": "a", "score": 1.0}, {"id": "b", "score": 2.5}]
    path = tmp_path / "out.parquet"

    frame = write_dicts_parquet(path, records)

    assert path.exists()
    assert len(frame) == 2
    read_back = pl.read_parquet(path)
    assert list(read_back["id"]) == ["a", "b"]


def test_write_dicts_parquet_empty(tmp_path):
    """write_dicts_parquet on empty list produces an empty DataFrame file."""
    from internal.storage.usecase.write_parquet import write_dicts_parquet

    path = tmp_path / "empty.parquet"
    frame = write_dicts_parquet(path, [])

    assert path.exists()
    assert len(frame) == 0


def test_write_dicts_parquet_creates_parent(tmp_path):
    """write_dicts_parquet creates missing parent directories."""
    from internal.storage.usecase.write_parquet import write_dicts_parquet

    path = tmp_path / "deep" / "nested" / "out.parquet"
    write_dicts_parquet(path, [{"x": 1}])

    assert path.exists()


def test_write_models_parquet(tmp_path):
    """write_models_parquet serialises Pydantic models correctly."""
    from internal.storage.usecase.write_parquet import write_models_parquet

    models = [_SampleModel(id="m1", value=0.5), _SampleModel(id="m2", value=1.5)]
    path = tmp_path / "models.parquet"

    frame = write_models_parquet(path, models)

    assert path.exists()
    assert len(frame) == 2
    assert list(frame["id"]) == ["m1", "m2"]


# ---------------------------------------------------------------------------
# write_jsonl / write_text_if_changed
# ---------------------------------------------------------------------------


def test_write_jsonl_basic(tmp_path):
    """write_jsonl writes valid JSONL readable back as Python dicts."""
    from internal.storage.usecase.write_jsonl import write_jsonl

    records = [{"a": 1}, {"b": "hello"}, {"c": True}]
    path = tmp_path / "out.jsonl"
    write_jsonl(path, records)

    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"b": "hello"}


def test_write_jsonl_empty(tmp_path):
    """write_jsonl on empty iterable writes an empty file."""
    from internal.storage.usecase.write_jsonl import write_jsonl

    path = tmp_path / "empty.jsonl"
    write_jsonl(path, [])
    assert path.exists()
    assert path.read_text() == ""


def test_write_text_if_changed_first_write(tmp_path):
    """write_text_if_changed returns True when writing a new file."""
    from internal.storage.usecase.write_jsonl import write_text_if_changed

    path = tmp_path / "text.txt"
    result = write_text_if_changed(path, "hello")

    assert result is True
    assert path.read_text() == "hello"


def test_write_text_if_changed_no_op_when_same(tmp_path):
    """write_text_if_changed returns False if content is unchanged."""
    from internal.storage.usecase.write_jsonl import write_text_if_changed

    path = tmp_path / "text.txt"
    write_text_if_changed(path, "same content")
    result = write_text_if_changed(path, "same content")

    assert result is False


def test_write_text_if_changed_updates_when_different(tmp_path):
    """write_text_if_changed returns True when content differs."""
    from internal.storage.usecase.write_jsonl import write_text_if_changed

    path = tmp_path / "text.txt"
    write_text_if_changed(path, "old")
    result = write_text_if_changed(path, "new")

    assert result is True
    assert path.read_text() == "new"


# ---------------------------------------------------------------------------
# write_table_bundle
# ---------------------------------------------------------------------------


def test_write_table_bundle(tmp_path):
    """write_table_bundle writes each DataFrame as <name>.parquet and returns paths."""
    from internal.storage.usecase.write_table_bundle import write_table_bundle

    tables = {
        "mentions": pl.DataFrame({"id": ["a", "b"]}),
        "entities": pl.DataFrame({"name": ["X", "Y", "Z"]}),
    }
    output_dir = tmp_path / "bundle"
    table_paths = write_table_bundle(output_dir, tables)

    assert "mentions" in table_paths
    assert "entities" in table_paths
    assert table_paths["mentions"].name == "mentions.parquet"
    assert table_paths["entities"].name == "entities.parquet"
    assert pl.read_parquet(table_paths["mentions"]).shape == (2, 1)
    assert pl.read_parquet(table_paths["entities"]).shape == (3, 1)


def test_write_table_bundle_empty_dict(tmp_path):
    """write_table_bundle on empty tables dict returns empty mapping."""
    from internal.storage.usecase.write_table_bundle import write_table_bundle

    result = write_table_bundle(tmp_path / "empty", {})
    assert result == {}


# ---------------------------------------------------------------------------
# StorageRepository
# ---------------------------------------------------------------------------


def test_storage_repository_implements_interface():
    """StorageRepository must be an instance of IStorageRepository."""
    from internal.storage.interface import IStorageRepository
    from internal.storage.usecase.usecase import StorageRepository

    repo = StorageRepository()
    assert isinstance(repo, IStorageRepository)


def test_new_storage_repository_returns_repository():
    """new_storage_repository() must return a StorageRepository."""
    from internal.storage.usecase.new import new_storage_repository
    from internal.storage.usecase.usecase import StorageRepository

    repo = new_storage_repository()
    assert isinstance(repo, StorageRepository)


def test_storage_repository_write_parquet_roundtrip(tmp_path):
    """StorageRepository.write_parquet delegates correctly."""
    from internal.storage.usecase.new import new_storage_repository

    repo = new_storage_repository()
    path = tmp_path / "test.parquet"
    frame = repo.write_parquet(path, [{"x": 10, "y": 20}])

    assert path.exists()
    assert len(frame) == 1
    assert frame["x"][0] == 10


def test_storage_repository_write_jsonl_roundtrip(tmp_path):
    """StorageRepository.write_jsonl delegates correctly."""
    from internal.storage.usecase.new import new_storage_repository

    repo = new_storage_repository()
    path = tmp_path / "test.jsonl"
    repo.write_jsonl(path, [{"key": "value"}])

    lines = path.read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"key": "value"}

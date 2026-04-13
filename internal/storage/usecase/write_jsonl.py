"""storage/usecase/write_jsonl.py — write records as newline-delimited JSON."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from internal.storage.errors import JsonlWriteError


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    """Write *records* to *path* as newline-delimited JSON (JSONL).

    The file is written atomically (full content built in memory first).
    Raises :class:`JsonlWriteError` on I/O failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        path.write_text(payload, encoding="utf-8")
    except Exception as exc:
        raise JsonlWriteError(f"Failed to write JSONL to {path}: {exc}") from exc


def write_text_if_changed(path: Path, payload: str) -> bool:
    """Write *payload* to *path* only if content differs from existing file.

    Returns ``True`` if the file was written, ``False`` if unchanged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == payload:
            return False
    path.write_text(payload, encoding="utf-8")
    return True


__all__ = ["write_jsonl", "write_text_if_changed"]

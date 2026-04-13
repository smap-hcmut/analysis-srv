"""helpers.py — shared utility helpers for reporting usecases."""

from __future__ import annotations

from typing import Any

from internal.reporting.type import ReportWindow


def _safe_float(value: Any) -> float | None:
    """Return float if value is numeric, else None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _top_n_rows(rows: list, n: int = 10) -> list:
    """Return first n rows (rows assumed already ranked)."""
    return rows[:n]


def _window_to_str(window: ReportWindow) -> str:
    """Return a human-readable string for an analysis window."""
    if window.analysis_start and window.analysis_end:
        return f"{window.analysis_start} to {window.analysis_end}"
    if window.analysis_start:
        return f"from {window.analysis_start}"
    if window.analysis_end:
        return f"until {window.analysis_end}"
    return "all_time"


__all__ = ["_safe_float", "_top_n_rows", "_window_to_str"]

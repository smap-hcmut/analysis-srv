from __future__ import annotations

from typing import Any


def fmt_number(value: int | float) -> str:
    n = float(value)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"


def percent_change(current: int | float, previous: int | float) -> float:
    current_n = float(current)
    previous_n = float(previous)
    if previous_n == 0:
        return 100.0 if current_n > 0 else 0.0
    return round(((current_n - previous_n) / previous_n) * 100, 1)


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        raw = value.strip()
        if not raw or raw == "{}":
            return []
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        return [part for part in raw.split(",") if part]
    return []

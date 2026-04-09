"""Canonical UTC timestamp utilities.

Single source of truth for UTC-now formatting across the service.
All timestamps use RFC3339 with Z suffix (no microseconds, no +00:00 offset).
"""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return current UTC time as an RFC3339 string with Z suffix.

    Example: "2026-04-09T14:30:22Z"
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def datetime_to_iso(dt: datetime | None) -> str:
    """Convert a datetime to RFC3339 UTC string. Returns empty string if None."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["utc_now_iso", "datetime_to_iso"]

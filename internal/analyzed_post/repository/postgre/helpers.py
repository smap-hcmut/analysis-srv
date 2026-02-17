"""Private helpers for analyzed_post PostgreSQL repository.

Data sanitization, UUID validation, datetime parsing.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional

# Compiled UUID pattern (reuse, don't recompile)
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_UUID_EXACT_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_NULL_STRING = "NULL"
_DATETIME_FIELDS = [
    "published_at",
    "analyzed_at",
    "crawled_at",
    "created_at",
    "updated_at",
]


def is_valid_uuid(value: str) -> bool:
    """Check if string is valid UUID format."""
    return bool(_UUID_EXACT_PATTERN.match(value))


def extract_uuid(value: str) -> Optional[str]:
    """Extract first UUID from string."""
    match = _UUID_PATTERN.search(value)
    return match.group(0) if match else None


def sanitize_project_id(data: Dict[str, Any]) -> None:
    """Sanitize project_id to ensure valid UUID format. Modifies in place.

    Raises:
        ValueError: If project_id contains no valid UUID
    """
    project_id = data.get("project_id")
    if not project_id:
        return

    if is_valid_uuid(project_id):
        return

    sanitized = extract_uuid(project_id)
    if sanitized:
        data["project_id"] = sanitized
    else:
        raise ValueError(
            f"Invalid project_id format, cannot extract UUID: {project_id}"
        )


def sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize analytics data for DB insertion.

    - Convert "NULL" strings to None
    - Ensure id is string
    - Parse datetime strings
    """
    sanitized = data.copy()

    for key, value in sanitized.items():
        if isinstance(value, str) and value.upper() == _NULL_STRING:
            sanitized[key] = None

    if "id" in sanitized and sanitized["id"] is not None:
        sanitized["id"] = str(sanitized["id"])

    for field in _DATETIME_FIELDS:
        if field in sanitized and isinstance(sanitized[field], str):
            try:
                sanitized[field] = datetime.fromisoformat(
                    sanitized[field].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                sanitized[field] = None

    return sanitized


__all__ = [
    "is_valid_uuid",
    "extract_uuid",
    "sanitize_project_id",
    "sanitize_data",
]

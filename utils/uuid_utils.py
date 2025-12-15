"""UUID validation and extraction utilities.

This module provides functions to validate and extract UUIDs from strings,
particularly useful for handling malformed project_id values from upstream services.
"""

from __future__ import annotations

import re
from typing import Optional

# Pre-compiled regex for performance
# Matches standard UUID format: 8-4-4-4-12 hex characters
_UUID_PATTERN = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)

_FULL_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def extract_uuid(value: str) -> Optional[str]:
    """Extract a valid UUID from a string.

    Searches for the first valid UUID pattern in the input string.
    Useful for extracting UUIDs from malformed values like
    "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor".

    Args:
        value: String that may contain a UUID.

    Returns:
        The extracted UUID in lowercase, or None if no valid UUID found.

    Examples:
        >>> extract_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80")
        'fc5d5ffb-36cc-4c8d-a288-f5215af7fb80'
        >>> extract_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor")
        'fc5d5ffb-36cc-4c8d-a288-f5215af7fb80'
        >>> extract_uuid("invalid-string")
        None
    """
    if not value:
        return None

    match = _UUID_PATTERN.search(value.strip())
    return match.group(1).lower() if match else None


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID format.

    Validates that the entire string matches the UUID format (8-4-4-4-12).
    Does not accept UUIDs with extra characters.

    Args:
        value: String to validate.

    Returns:
        True if the string is a valid UUID, False otherwise.

    Examples:
        >>> is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80")
        True
        >>> is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor")
        False
        >>> is_valid_uuid("")
        False
    """
    if not value:
        return False

    return bool(_FULL_UUID_PATTERN.match(value.strip()))

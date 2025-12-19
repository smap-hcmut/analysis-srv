"""Custom JSON encoder for Analytics Engine.

This module provides custom JSON encoding to handle:
1. BigInt values that exceed JavaScript's Number.MAX_SAFE_INTEGER
2. Datetime objects
3. UUID objects
4. Decimal values
"""

from __future__ import annotations

import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from uuid import UUID

# JavaScript's maximum safe integer (2^53 - 1)
JS_MAX_SAFE_INTEGER = 9007199254740991


class BigIntEncoder(json.JSONEncoder):
    """JSON encoder that serializes large integers as strings.

    This encoder converts integers exceeding JavaScript's MAX_SAFE_INTEGER
    to strings to prevent precision loss in JavaScript clients.

    Also handles:
    - datetime/date objects → ISO 8601 strings
    - UUID objects → string representation
    - Decimal objects → float

    Example:
        >>> import json
        >>> data = {"id": 7576276451171880962, "name": "test"}
        >>> json.dumps(data, cls=BigIntEncoder)
        '{"id": "7576276451171880962", "name": "test"}'
    """

    def default(self, obj: Any) -> Any:
        """Convert non-serializable objects to JSON-compatible types.

        Args:
            obj: Object to serialize.

        Returns:
            JSON-compatible representation of the object.

        Raises:
            TypeError: If object type is not supported.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()

        if isinstance(obj, date):
            return obj.isoformat()

        if isinstance(obj, UUID):
            return str(obj)

        if isinstance(obj, Decimal):
            return float(obj)

        return super().default(obj)

    def encode(self, obj: Any) -> str:
        """Encode object to JSON string.

        Overrides default encode to handle BigInt values in nested structures.

        Args:
            obj: Object to encode.

        Returns:
            JSON string representation.
        """
        return super().encode(self._convert_bigints(obj))

    def _convert_bigints(self, obj: Any) -> Any:
        """Recursively convert BigInt values to strings.

        Args:
            obj: Object to process.

        Returns:
            Object with BigInt values converted to strings.
        """
        if isinstance(obj, dict):
            return {key: self._convert_bigints(value) for key, value in obj.items()}

        if isinstance(obj, list):
            return [self._convert_bigints(item) for item in obj]

        if isinstance(obj, int) and obj > JS_MAX_SAFE_INTEGER:
            return str(obj)

        return obj


def dumps_safe(obj: Any, **kwargs) -> str:
    """Serialize object to JSON string with BigInt safety.

    Convenience function that uses BigIntEncoder by default.

    Args:
        obj: Object to serialize.
        **kwargs: Additional arguments passed to json.dumps.

    Returns:
        JSON string with BigInt values as strings.

    Example:
        >>> dumps_safe({"id": 7576276451171880962})
        '{"id": "7576276451171880962"}'
    """
    kwargs.setdefault("cls", BigIntEncoder)
    return json.dumps(obj, **kwargs)


def sanitize_null_string(value: Any) -> Any:
    """Convert string "NULL" to Python None.

    Args:
        value: Value to sanitize.

    Returns:
        None if value is string "NULL" or "null", otherwise original value.

    Examples:
        >>> sanitize_null_string("NULL")
        None
        >>> sanitize_null_string("null")
        None
        >>> sanitize_null_string("actual value")
        'actual value'
        >>> sanitize_null_string(None)
        None
    """
    if isinstance(value, str) and value.upper() == "NULL":
        return None
    return value


def sanitize_boolean(value: Any) -> bool:
    """Convert string boolean to Python bool.

    Args:
        value: Value to convert.

    Returns:
        Boolean value.

    Examples:
        >>> sanitize_boolean("True")
        True
        >>> sanitize_boolean("false")
        False
        >>> sanitize_boolean(True)
        True
        >>> sanitize_boolean(1)
        True
    """
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value) if value is not None else False


def sanitize_analytics_data(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize analytics data before saving to database.

    Ensures:
    - ID fields are strings (prevent BigInt precision loss)
    - Boolean fields are actual booleans (not strings "True"/"False")
    - NULL string values are converted to Python None
    - Empty strings are preserved (not converted to NULL)

    Args:
        data: Analytics data dictionary.

    Returns:
        Sanitized data with proper types.
    """
    sanitized = data.copy()

    # Ensure ID is string
    if "id" in sanitized and sanitized["id"] is not None:
        sanitized["id"] = str(sanitized["id"])

    # Ensure boolean fields are actual booleans
    bool_fields = ["is_viral", "is_kol"]
    for field in bool_fields:
        if field in sanitized:
            value = sanitized[field]
            if value is not None:
                sanitized[field] = sanitize_boolean(value)

    # Sanitize NULL string values for nullable fields
    null_string_fields = [
        "job_id",
        "batch_index",
        "task_type",
        "keyword_source",
        "crawled_at",
        "pipeline_version",
        "fetch_error",
        "error_code",
        "error_details",
        "project_id",
    ]
    for field in null_string_fields:
        if field in sanitized:
            sanitized[field] = sanitize_null_string(sanitized[field])

    return sanitized


def serialize_analytics_result(result: dict[str, Any]) -> dict[str, Any]:
    """Serialize analytics result with proper type handling.

    This is an alias for sanitize_analytics_data for backward compatibility.

    Ensures:
    - ID fields are strings (prevent BigInt precision loss)
    - Boolean fields are actual booleans (not strings)
    - NULL values are None (not string "NULL")

    Args:
        result: Analytics result dictionary.

    Returns:
        Serialized result with proper types.
    """
    return sanitize_analytics_data(result)

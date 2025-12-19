"""Post ID validation and serialization utilities.

This module provides functions to validate, serialize, and detect issues with
social media post IDs, particularly for platforms like TikTok that use large
numeric IDs that exceed JavaScript's Number.MAX_SAFE_INTEGER.

JavaScript's Number.MAX_SAFE_INTEGER is 9007199254740991 (2^53 - 1, 16 digits).
TikTok IDs are typically 19 digits, causing precision loss when serialized as JSON numbers.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from core.logger import logger

# JavaScript's maximum safe integer (2^53 - 1)
JS_MAX_SAFE_INTEGER = 9007199254740991

# Pattern for detecting potentially truncated IDs (ending with 3+ zeros)
_TRUNCATED_ID_PATTERN = re.compile(r"^(\d+)0{3,}$")

# Platform-specific ID patterns
_TIKTOK_ID_PATTERN = re.compile(r"^\d{17,20}$")  # TikTok IDs are 17-20 digits
_GENERIC_NUMERIC_ID_PATTERN = re.compile(r"^\d+$")


def ensure_string_id(post_id: any) -> str:
    """Ensure post ID is serialized as string to prevent precision loss.

    Converts numeric IDs to strings to prevent JavaScript precision loss
    when IDs exceed Number.MAX_SAFE_INTEGER.

    Args:
        post_id: Post ID as string, int, or any type.

    Returns:
        Post ID as string.

    Examples:
        >>> ensure_string_id(7576276451171880962)
        '7576276451171880962'
        >>> ensure_string_id("7576276451171880962")
        '7576276451171880962'
        >>> ensure_string_id(None)
        ''
    """
    if post_id is None:
        return ""

    return str(post_id)


def is_bigint_id(post_id: any) -> bool:
    """Check if post ID exceeds JavaScript's safe integer limit.

    Args:
        post_id: Post ID as string or int.

    Returns:
        True if ID exceeds JS_MAX_SAFE_INTEGER, False otherwise.

    Examples:
        >>> is_bigint_id(7576276451171880962)
        True
        >>> is_bigint_id(123456789)
        False
        >>> is_bigint_id("7576276451171880962")
        True
    """
    if post_id is None:
        return False

    try:
        numeric_id = int(post_id)
        return numeric_id > JS_MAX_SAFE_INTEGER
    except (ValueError, TypeError):
        return False


def detect_truncated_id(post_id: str) -> Tuple[bool, Optional[str]]:
    """Detect if an ID appears to be truncated due to precision loss.

    IDs that end with multiple zeros (3+) may indicate precision loss
    from JavaScript number conversion.

    Args:
        post_id: Post ID as string.

    Returns:
        Tuple of (is_truncated, warning_message).
        is_truncated is True if ID appears truncated.
        warning_message contains details if truncated, None otherwise.

    Examples:
        >>> detect_truncated_id("7576276451171880000")
        (True, "ID '7576276451171880000' ends with 3+ zeros, possible precision loss")
        >>> detect_truncated_id("7576276451171880962")
        (False, None)
    """
    if not post_id:
        return False, None

    str_id = str(post_id)
    match = _TRUNCATED_ID_PATTERN.match(str_id)

    if match:
        warning = f"ID '{str_id}' ends with 3+ zeros, possible precision loss"
        return True, warning

    return False, None


def validate_tiktok_id(post_id: str) -> Tuple[bool, Optional[str]]:
    """Validate TikTok post ID format.

    TikTok IDs are typically 17-20 digit numeric strings.

    Args:
        post_id: Post ID to validate.

    Returns:
        Tuple of (is_valid, error_message).
        is_valid is True if ID matches expected format.
        error_message contains details if invalid, None otherwise.

    Examples:
        >>> validate_tiktok_id("7576276451171880962")
        (True, None)
        >>> validate_tiktok_id("123")
        (False, "TikTok ID '123' does not match expected format (17-20 digits)")
    """
    if not post_id:
        return False, "Post ID is empty or None"

    str_id = str(post_id)

    if not _TIKTOK_ID_PATTERN.match(str_id):
        return False, f"TikTok ID '{str_id}' does not match expected format (17-20 digits)"

    return True, None


def validate_post_id(post_id: str, platform: str = "UNKNOWN") -> Tuple[bool, Optional[str]]:
    """Validate post ID format based on platform.

    Args:
        post_id: Post ID to validate.
        platform: Platform name (TIKTOK, FACEBOOK, etc.).

    Returns:
        Tuple of (is_valid, error_message).

    Examples:
        >>> validate_post_id("7576276451171880962", "TIKTOK")
        (True, None)
        >>> validate_post_id("abc123", "TIKTOK")
        (False, "TikTok ID 'abc123' does not match expected format (17-20 digits)")
    """
    if not post_id:
        return False, "Post ID is empty or None"

    platform_upper = str(platform).upper()

    if platform_upper == "TIKTOK":
        return validate_tiktok_id(post_id)

    # For other platforms, just check it's not empty
    return True, None


def log_id_warnings(post_id: str, platform: str = "UNKNOWN") -> None:
    """Log warnings for potential ID issues.

    Checks for truncation and logs appropriate warnings.

    Args:
        post_id: Post ID to check.
        platform: Platform name for context.
    """
    if not post_id:
        return

    str_id = str(post_id)

    # Check for truncation
    is_truncated, warning = detect_truncated_id(str_id)
    if is_truncated:
        logger.warning(
            "Potential ID precision loss detected: %s (platform=%s)",
            warning,
            platform,
        )

    # Check if BigInt
    if is_bigint_id(str_id):
        logger.debug(
            "BigInt ID detected: %s (platform=%s), ensure string serialization",
            str_id,
            platform,
        )

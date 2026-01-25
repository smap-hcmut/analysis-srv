"""Unit tests for ID utilities.

Tests for BigInt ID handling, truncation detection, and platform-specific validation.
"""

import pytest

from utils.id_utils import (
    ensure_string_id,
    is_bigint_id,
    detect_truncated_id,
    validate_tiktok_id,
    validate_post_id,
    JS_MAX_SAFE_INTEGER,
)


class TestEnsureStringId:
    """Tests for ensure_string_id function."""

    def test_converts_int_to_string(self):
        """Should convert integer ID to string."""
        assert ensure_string_id(7576276451171880962) == "7576276451171880962"

    def test_preserves_string_id(self):
        """Should preserve string ID as-is."""
        assert ensure_string_id("7576276451171880962") == "7576276451171880962"

    def test_handles_none(self):
        """Should return empty string for None."""
        assert ensure_string_id(None) == ""

    def test_handles_small_int(self):
        """Should convert small integer to string."""
        assert ensure_string_id(123456789) == "123456789"


class TestIsBigintId:
    """Tests for is_bigint_id function."""

    def test_detects_bigint(self):
        """Should detect ID exceeding JS MAX_SAFE_INTEGER."""
        # TikTok ID (19 digits) exceeds JS_MAX_SAFE_INTEGER
        assert is_bigint_id(7576276451171880962) is True

    def test_detects_safe_int(self):
        """Should return False for safe integers."""
        assert is_bigint_id(123456789) is False

    def test_handles_string_bigint(self):
        """Should detect BigInt from string representation."""
        assert is_bigint_id("7576276451171880962") is True

    def test_handles_string_safe_int(self):
        """Should return False for safe integer string."""
        assert is_bigint_id("123456789") is False

    def test_handles_none(self):
        """Should return False for None."""
        assert is_bigint_id(None) is False

    def test_boundary_value(self):
        """Should correctly handle boundary value."""
        assert is_bigint_id(JS_MAX_SAFE_INTEGER) is False
        assert is_bigint_id(JS_MAX_SAFE_INTEGER + 1) is True


class TestDetectTruncatedId:
    """Tests for detect_truncated_id function."""

    def test_detects_truncated_id(self):
        """Should detect ID ending with 3+ zeros."""
        is_truncated, warning = detect_truncated_id("7576276451171880000")
        assert is_truncated is True
        assert "precision loss" in warning.lower()

    def test_normal_id_not_truncated(self):
        """Should not flag normal ID as truncated."""
        is_truncated, warning = detect_truncated_id("7576276451171880962")
        assert is_truncated is False
        assert warning is None

    def test_id_ending_with_two_zeros(self):
        """Should not flag ID ending with only 2 zeros."""
        is_truncated, warning = detect_truncated_id("7576276451171880900")
        assert is_truncated is False

    def test_handles_empty_string(self):
        """Should handle empty string."""
        is_truncated, warning = detect_truncated_id("")
        assert is_truncated is False
        assert warning is None

    def test_handles_none(self):
        """Should handle None."""
        is_truncated, warning = detect_truncated_id(None)
        assert is_truncated is False


class TestValidateTiktokId:
    """Tests for validate_tiktok_id function."""

    def test_valid_19_digit_id(self):
        """Should accept valid 19-digit TikTok ID."""
        is_valid, error = validate_tiktok_id("7576276451171880962")
        assert is_valid is True
        assert error is None

    def test_valid_17_digit_id(self):
        """Should accept valid 17-digit TikTok ID."""
        is_valid, error = validate_tiktok_id("12345678901234567")
        assert is_valid is True

    def test_valid_20_digit_id(self):
        """Should accept valid 20-digit TikTok ID."""
        is_valid, error = validate_tiktok_id("12345678901234567890")
        assert is_valid is True

    def test_rejects_short_id(self):
        """Should reject ID shorter than 17 digits."""
        is_valid, error = validate_tiktok_id("123")
        assert is_valid is False
        assert "17-20 digits" in error

    def test_rejects_non_numeric_id(self):
        """Should reject non-numeric ID."""
        is_valid, error = validate_tiktok_id("abc123def456")
        assert is_valid is False

    def test_rejects_empty_id(self):
        """Should reject empty ID."""
        is_valid, error = validate_tiktok_id("")
        assert is_valid is False


class TestValidatePostId:
    """Tests for validate_post_id function."""

    def test_validates_tiktok_id(self):
        """Should validate TikTok ID format."""
        is_valid, error = validate_post_id("7576276451171880962", "TIKTOK")
        assert is_valid is True

    def test_validates_tiktok_lowercase(self):
        """Should handle lowercase platform name."""
        is_valid, error = validate_post_id("7576276451171880962", "tiktok")
        assert is_valid is True

    def test_accepts_any_id_for_unknown_platform(self):
        """Should accept any non-empty ID for unknown platform."""
        is_valid, error = validate_post_id("any-id-format", "UNKNOWN")
        assert is_valid is True

    def test_rejects_empty_id(self):
        """Should reject empty ID for any platform."""
        is_valid, error = validate_post_id("", "TIKTOK")
        assert is_valid is False

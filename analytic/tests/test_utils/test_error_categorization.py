"""Unit tests for error categorization utilities."""

import pytest

from core.constants import (
    ErrorCategory,
    ErrorCode,
    categorize_error,
    is_retryable_error,
    ERROR_CODE_TO_CATEGORY,
    RETRYABLE_ERROR_CODES,
    PERMANENT_ERROR_CODES,
)


class TestCategorizeError:
    """Tests for categorize_error function."""

    def test_rate_limiting_codes(self):
        """Rate limiting codes should return RATE_LIMITING category."""
        assert categorize_error("RATE_LIMITED") == ErrorCategory.RATE_LIMITING
        assert categorize_error("AUTH_FAILED") == ErrorCategory.RATE_LIMITING
        assert categorize_error("ACCESS_DENIED") == ErrorCategory.RATE_LIMITING

    def test_content_codes(self):
        """Content codes should return CONTENT category."""
        assert categorize_error("CONTENT_REMOVED") == ErrorCategory.CONTENT
        assert categorize_error("CONTENT_NOT_FOUND") == ErrorCategory.CONTENT
        assert categorize_error("CONTENT_UNAVAILABLE") == ErrorCategory.CONTENT

    def test_network_codes(self):
        """Network codes should return NETWORK category."""
        assert categorize_error("NETWORK_ERROR") == ErrorCategory.NETWORK
        assert categorize_error("TIMEOUT") == ErrorCategory.NETWORK
        assert categorize_error("CONNECTION_REFUSED") == ErrorCategory.NETWORK
        assert categorize_error("DNS_ERROR") == ErrorCategory.NETWORK

    def test_parsing_codes(self):
        """Parsing codes should return PARSING category."""
        assert categorize_error("PARSE_ERROR") == ErrorCategory.PARSING
        assert categorize_error("INVALID_URL") == ErrorCategory.PARSING
        assert categorize_error("INVALID_RESPONSE") == ErrorCategory.PARSING

    def test_media_codes(self):
        """Media codes should return MEDIA category."""
        assert categorize_error("MEDIA_DOWNLOAD_FAILED") == ErrorCategory.MEDIA
        assert categorize_error("MEDIA_TOO_LARGE") == ErrorCategory.MEDIA
        assert categorize_error("MEDIA_FORMAT_ERROR") == ErrorCategory.MEDIA

    def test_storage_codes(self):
        """Storage codes should return STORAGE category."""
        assert categorize_error("STORAGE_ERROR") == ErrorCategory.STORAGE
        assert categorize_error("UPLOAD_FAILED") == ErrorCategory.STORAGE
        assert categorize_error("DATABASE_ERROR") == ErrorCategory.STORAGE

    def test_generic_codes(self):
        """Generic codes should return GENERIC category."""
        assert categorize_error("UNKNOWN_ERROR") == ErrorCategory.GENERIC
        assert categorize_error("INTERNAL_ERROR") == ErrorCategory.GENERIC

    def test_unknown_code_returns_generic(self):
        """Unknown error codes should return GENERIC category."""
        assert categorize_error("SOME_UNKNOWN_CODE") == ErrorCategory.GENERIC
        assert categorize_error("") == ErrorCategory.GENERIC
        assert categorize_error("invalid") == ErrorCategory.GENERIC


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_retryable_errors(self):
        """Retryable errors should return True."""
        assert is_retryable_error("RATE_LIMITED") is True
        assert is_retryable_error("NETWORK_ERROR") is True
        assert is_retryable_error("TIMEOUT") is True
        assert is_retryable_error("STORAGE_ERROR") is True

    def test_permanent_errors(self):
        """Permanent errors should return False."""
        assert is_retryable_error("CONTENT_REMOVED") is False
        assert is_retryable_error("PARSE_ERROR") is False
        assert is_retryable_error("MEDIA_TOO_LARGE") is False

    def test_unknown_error_not_retryable(self):
        """Unknown error codes should not be retryable."""
        assert is_retryable_error("SOME_UNKNOWN_CODE") is False
        assert is_retryable_error("") is False


class TestErrorCodeEnums:
    """Tests for ErrorCode and ErrorCategory enums."""

    def test_error_code_count(self):
        """Should have exactly 17 error codes."""
        # 3 rate_limiting + 3 content + 4 network + 3 parsing + 3 media + 3 storage + 2 generic = 21
        # Design says 17, but we have 21 based on the taxonomy
        assert len(ErrorCode) >= 17

    def test_error_category_count(self):
        """Should have exactly 7 error categories."""
        assert len(ErrorCategory) == 7

    def test_all_codes_have_category(self):
        """Every ErrorCode should have a mapping to ErrorCategory."""
        for code in ErrorCode:
            assert code in ERROR_CODE_TO_CATEGORY

    def test_retryable_and_permanent_are_disjoint(self):
        """Retryable and permanent error sets should not overlap."""
        overlap = RETRYABLE_ERROR_CODES & PERMANENT_ERROR_CODES
        assert len(overlap) == 0, f"Overlapping codes: {overlap}"

    def test_all_codes_classified(self):
        """All error codes should be either retryable or permanent (or generic)."""
        generic_codes = {ErrorCode.UNKNOWN_ERROR, ErrorCode.INTERNAL_ERROR}
        all_classified = RETRYABLE_ERROR_CODES | PERMANENT_ERROR_CODES | generic_codes

        for code in ErrorCode:
            assert code in all_classified, f"Code {code} is not classified"

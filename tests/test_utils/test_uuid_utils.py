"""Unit tests for UUID utilities."""

import pytest

from utils.uuid_utils import extract_uuid, is_valid_uuid


class TestExtractUuid:
    """Tests for extract_uuid function."""

    def test_extract_valid_uuid(self):
        """Should return UUID as-is when input is valid."""
        uuid = "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"
        assert extract_uuid(uuid) == uuid

    def test_extract_uuid_with_competitor_suffix(self):
        """Should extract UUID from string with -competitor suffix."""
        value = "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor"
        assert extract_uuid(value) == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_extract_uuid_with_competitor_name_suffix(self):
        """Should extract UUID from job_id format with competitor name."""
        value = "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor-Misa-0"
        assert extract_uuid(value) == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_extract_uuid_with_brand_suffix(self):
        """Should extract UUID from job_id format with brand."""
        value = "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-brand-0"
        assert extract_uuid(value) == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_extract_uuid_uppercase(self):
        """Should handle uppercase UUIDs and return lowercase."""
        value = "FC5D5FFB-36CC-4C8D-A288-F5215AF7FB80-competitor"
        assert extract_uuid(value) == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_extract_uuid_with_whitespace(self):
        """Should handle leading/trailing whitespace."""
        value = "  fc5d5ffb-36cc-4c8d-a288-f5215af7fb80  "
        assert extract_uuid(value) == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"

    def test_extract_uuid_invalid_string(self):
        """Should return None for string without valid UUID."""
        assert extract_uuid("invalid-string") is None
        assert extract_uuid("not-a-uuid-at-all") is None

    def test_extract_uuid_empty_string(self):
        """Should return None for empty string."""
        assert extract_uuid("") is None

    def test_extract_uuid_none(self):
        """Should return None for None input."""
        assert extract_uuid(None) is None

    def test_extract_uuid_partial_uuid(self):
        """Should return None for partial UUID."""
        assert extract_uuid("fc5d5ffb-36cc-4c8d") is None

    def test_extract_uuid_multiple_uuids(self):
        """Should return first UUID when multiple present."""
        value = "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-abc12345-1234-5678-9abc-def012345678"
        assert extract_uuid(value) == "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80"


class TestIsValidUuid:
    """Tests for is_valid_uuid function."""

    def test_valid_uuid(self):
        """Should return True for valid UUID."""
        assert is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80") is True

    def test_valid_uuid_uppercase(self):
        """Should return True for uppercase UUID."""
        assert is_valid_uuid("FC5D5FFB-36CC-4C8D-A288-F5215AF7FB80") is True

    def test_valid_uuid_with_whitespace(self):
        """Should handle leading/trailing whitespace."""
        assert is_valid_uuid("  fc5d5ffb-36cc-4c8d-a288-f5215af7fb80  ") is True

    def test_invalid_uuid_with_suffix(self):
        """Should return False for UUID with extra suffix."""
        assert is_valid_uuid("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80-competitor") is False

    def test_invalid_uuid_with_prefix(self):
        """Should return False for UUID with prefix."""
        assert is_valid_uuid("prefix-fc5d5ffb-36cc-4c8d-a288-f5215af7fb80") is False

    def test_invalid_string(self):
        """Should return False for non-UUID string."""
        assert is_valid_uuid("invalid-string") is False

    def test_empty_string(self):
        """Should return False for empty string."""
        assert is_valid_uuid("") is False

    def test_none_value(self):
        """Should return False for None."""
        assert is_valid_uuid(None) is False

    def test_partial_uuid(self):
        """Should return False for partial UUID."""
        assert is_valid_uuid("fc5d5ffb-36cc-4c8d") is False

    def test_uuid_without_dashes(self):
        """Should return False for UUID without dashes."""
        assert is_valid_uuid("fc5d5ffb36cc4c8da288f5215af7fb80") is False

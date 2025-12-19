"""Unit tests for JSON encoder and data sanitization utilities.

Tests for BigInt encoding, NULL string sanitization, and boolean handling.
"""

import json
import pytest
from datetime import datetime
from uuid import UUID

from utils.json_encoder import (
    BigIntEncoder,
    dumps_safe,
    sanitize_null_string,
    sanitize_boolean,
    sanitize_analytics_data,
    serialize_analytics_result,
    JS_MAX_SAFE_INTEGER,
)


class TestSanitizeNullString:
    """Tests for sanitize_null_string function."""

    def test_converts_null_string_uppercase(self):
        """Should convert 'NULL' string to None."""
        assert sanitize_null_string("NULL") is None

    def test_converts_null_string_lowercase(self):
        """Should convert 'null' string to None."""
        assert sanitize_null_string("null") is None

    def test_converts_null_string_mixed_case(self):
        """Should convert 'Null' string to None."""
        assert sanitize_null_string("Null") is None

    def test_preserves_actual_none(self):
        """Should preserve actual None value."""
        assert sanitize_null_string(None) is None

    def test_preserves_actual_value(self):
        """Should preserve actual string value."""
        assert sanitize_null_string("actual value") == "actual value"

    def test_preserves_empty_string(self):
        """Should preserve empty string (not convert to None)."""
        assert sanitize_null_string("") == ""

    def test_preserves_integer(self):
        """Should preserve integer value."""
        assert sanitize_null_string(123) == 123


class TestSanitizeBoolean:
    """Tests for sanitize_boolean function."""

    def test_converts_true_string_uppercase(self):
        """Should convert 'True' string to True."""
        assert sanitize_boolean("True") is True

    def test_converts_true_string_lowercase(self):
        """Should convert 'true' string to True."""
        assert sanitize_boolean("true") is True

    def test_converts_false_string_uppercase(self):
        """Should convert 'False' string to False."""
        assert sanitize_boolean("False") is False

    def test_converts_false_string_lowercase(self):
        """Should convert 'false' string to False."""
        assert sanitize_boolean("false") is False

    def test_preserves_actual_true(self):
        """Should preserve actual True value."""
        assert sanitize_boolean(True) is True

    def test_preserves_actual_false(self):
        """Should preserve actual False value."""
        assert sanitize_boolean(False) is False

    def test_converts_truthy_int(self):
        """Should convert truthy integer to True."""
        assert sanitize_boolean(1) is True

    def test_converts_falsy_int(self):
        """Should convert falsy integer to False."""
        assert sanitize_boolean(0) is False

    def test_handles_none(self):
        """Should convert None to False."""
        assert sanitize_boolean(None) is False


class TestSanitizeAnalyticsData:
    """Tests for sanitize_analytics_data function."""

    def test_sanitizes_id_to_string(self):
        """Should convert ID to string."""
        data = {"id": 7576276451171880962}
        result = sanitize_analytics_data(data)
        assert result["id"] == "7576276451171880962"
        assert isinstance(result["id"], str)

    def test_sanitizes_boolean_fields(self):
        """Should convert string booleans to actual booleans."""
        data = {"is_viral": "True", "is_kol": "False"}
        result = sanitize_analytics_data(data)
        assert result["is_viral"] is True
        assert result["is_kol"] is False

    def test_sanitizes_null_string_fields(self):
        """Should convert 'NULL' strings to None."""
        data = {
            "job_id": "NULL",
            "batch_index": "NULL",
            "task_type": "null",
            "keyword_source": "NULL",
        }
        result = sanitize_analytics_data(data)
        assert result["job_id"] is None
        assert result["batch_index"] is None
        assert result["task_type"] is None
        assert result["keyword_source"] is None

    def test_preserves_actual_values(self):
        """Should preserve actual non-NULL values."""
        data = {
            "id": "7576276451171880962",
            "job_id": "proj_xyz-brand-0",
            "is_viral": True,
            "is_kol": False,
        }
        result = sanitize_analytics_data(data)
        assert result["id"] == "7576276451171880962"
        assert result["job_id"] == "proj_xyz-brand-0"
        assert result["is_viral"] is True
        assert result["is_kol"] is False

    def test_handles_missing_fields(self):
        """Should handle missing fields gracefully."""
        data = {"id": "123", "platform": "TIKTOK"}
        result = sanitize_analytics_data(data)
        assert result["id"] == "123"
        assert result["platform"] == "TIKTOK"
        assert "job_id" not in result

    def test_full_analytics_data(self):
        """Should sanitize complete analytics data."""
        data = {
            "id": 7576276451171880962,
            "project_id": "NULL",
            "is_viral": "False",
            "is_kol": "True",
            "job_id": "proj_xyz-brand-0",
            "batch_index": 1,
            "task_type": "research_and_crawl",
            "keyword_source": "VinFast VF8",
            "crawled_at": "NULL",
            "pipeline_version": "crawler_tiktok_v3",
        }
        result = sanitize_analytics_data(data)

        assert result["id"] == "7576276451171880962"
        assert result["project_id"] is None
        assert result["is_viral"] is False
        assert result["is_kol"] is True
        assert result["job_id"] == "proj_xyz-brand-0"
        assert result["batch_index"] == 1
        assert result["task_type"] == "research_and_crawl"
        assert result["keyword_source"] == "VinFast VF8"
        assert result["crawled_at"] is None
        assert result["pipeline_version"] == "crawler_tiktok_v3"


class TestBigIntEncoder:
    """Tests for BigIntEncoder class."""

    def test_encodes_bigint_as_string(self):
        """Should encode BigInt as string."""
        data = {"id": 7576276451171880962}
        result = json.dumps(data, cls=BigIntEncoder)
        assert '"7576276451171880962"' in result

    def test_preserves_safe_int(self):
        """Should preserve safe integers as numbers."""
        data = {"count": 123456}
        result = json.dumps(data, cls=BigIntEncoder)
        parsed = json.loads(result)
        assert parsed["count"] == 123456
        assert isinstance(parsed["count"], int)

    def test_encodes_datetime(self):
        """Should encode datetime as ISO string."""
        dt = datetime(2025, 12, 15, 10, 30, 0)
        data = {"timestamp": dt}
        result = json.dumps(data, cls=BigIntEncoder)
        assert "2025-12-15T10:30:00" in result

    def test_encodes_uuid(self):
        """Should encode UUID as string."""
        uuid_val = UUID("fc5d5ffb-36cc-4c8d-a288-f5215af7fb80")
        data = {"project_id": uuid_val}
        result = json.dumps(data, cls=BigIntEncoder)
        assert "fc5d5ffb-36cc-4c8d-a288-f5215af7fb80" in result

    def test_handles_nested_bigint(self):
        """Should handle BigInt in nested structures."""
        data = {
            "items": [
                {"id": 7576276451171880962},
                {"id": 7576276451171880963},
            ]
        }
        result = json.dumps(data, cls=BigIntEncoder)
        assert '"7576276451171880962"' in result
        assert '"7576276451171880963"' in result


class TestDumpsSafe:
    """Tests for dumps_safe function."""

    def test_uses_bigint_encoder(self):
        """Should use BigIntEncoder by default."""
        data = {"id": 7576276451171880962}
        result = dumps_safe(data)
        assert '"7576276451171880962"' in result

    def test_accepts_additional_kwargs(self):
        """Should pass additional kwargs to json.dumps."""
        data = {"id": 123, "name": "test"}
        result = dumps_safe(data, indent=2)
        assert "\n" in result  # Indented output has newlines

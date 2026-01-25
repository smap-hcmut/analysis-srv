"""Unit tests for project_id extraction utility.

Tests cover all job_id formats:
- Brand format: proj_xyz-brand-0
- Competitor format: proj_xyz-toyota-5
- Dry-run format: UUID
- Edge cases: empty, invalid, malformed
"""

import pytest

from utils.project_id_extractor import (
    extract_project_id,
    is_dry_run_job,
    parse_job_id,
)


class TestExtractProjectId:
    """Tests for extract_project_id function."""

    # Test case 1: Brand format
    def test_brand_format_simple(self):
        """Extract project_id from simple brand format."""
        assert extract_project_id("proj_abc123-brand-0") == "proj_abc123"

    # Test case 2: Brand format with index > 0
    def test_brand_format_with_index(self):
        """Extract project_id from brand format with higher index."""
        assert extract_project_id("proj_xyz-brand-5") == "proj_xyz"

    # Test case 3: Competitor format
    def test_competitor_format(self):
        """Extract project_id from competitor format."""
        assert extract_project_id("proj_xyz-toyota-5") == "proj_xyz"

    # Test case 4: Project ID with hyphens
    def test_project_id_with_hyphens(self):
        """Extract project_id that contains hyphens."""
        assert extract_project_id("my-project-name-competitor-10") == "my-project-name"

    # Test case 5: UUID (dry-run) returns None
    def test_uuid_dry_run_returns_none(self):
        """UUID job_id (dry-run) should return None."""
        assert extract_project_id("550e8400-e29b-41d4-a716-446655440000") is None

    # Test case 6: UUID uppercase
    def test_uuid_uppercase(self):
        """UUID in uppercase should also return None."""
        assert extract_project_id("550E8400-E29B-41D4-A716-446655440000") is None

    # Test case 7: Empty string
    def test_empty_string(self):
        """Empty string should return None."""
        assert extract_project_id("") is None

    # Test case 8: None input
    def test_none_input(self):
        """None input should return None."""
        assert extract_project_id(None) is None

    # Test case 9: Invalid format - no index
    def test_invalid_no_index(self):
        """Job ID without numeric index should return None."""
        assert extract_project_id("proj_xyz-brand") is None

    # Test case 10: Invalid format - non-numeric index
    def test_invalid_non_numeric_index(self):
        """Job ID with non-numeric index should return None."""
        assert extract_project_id("proj_xyz-brand-abc") is None

    # Test case 11: Too few parts
    def test_too_few_parts(self):
        """Job ID with less than 3 parts should return None."""
        assert extract_project_id("proj_xyz-0") is None

    # Test case 12: Whitespace handling
    def test_whitespace_handling(self):
        """Job ID with leading/trailing whitespace should be trimmed."""
        assert extract_project_id("  proj_abc-brand-0  ") == "proj_abc"

    # Test case 13: Complex project ID
    def test_complex_project_id(self):
        """Extract complex project_id with multiple hyphens."""
        assert extract_project_id("proj-2024-q1-campaign-brand-3") == "proj-2024-q1-campaign"


class TestIsDryRunJob:
    """Tests for is_dry_run_job function."""

    def test_uuid_is_dry_run(self):
        """UUID should be identified as dry-run."""
        assert is_dry_run_job("550e8400-e29b-41d4-a716-446655440000") is True

    def test_regular_job_not_dry_run(self):
        """Regular job_id should not be dry-run."""
        assert is_dry_run_job("proj_xyz-brand-0") is False

    def test_empty_not_dry_run(self):
        """Empty string should not be dry-run."""
        assert is_dry_run_job("") is False

    def test_none_not_dry_run(self):
        """None should not be dry-run."""
        assert is_dry_run_job(None) is False


class TestParseJobId:
    """Tests for parse_job_id function."""

    def test_parse_brand_format(self):
        """Parse brand format job_id."""
        result = parse_job_id("proj_abc-brand-0")
        assert result["project_id"] == "proj_abc"
        assert result["entity_name"] == "brand"
        assert result["index"] == 0
        assert result["is_dry_run"] is False

    def test_parse_competitor_format(self):
        """Parse competitor format job_id."""
        result = parse_job_id("proj_xyz-toyota-5")
        assert result["project_id"] == "proj_xyz"
        assert result["entity_name"] == "toyota"
        assert result["index"] == 5
        assert result["is_dry_run"] is False

    def test_parse_uuid_dry_run(self):
        """Parse UUID (dry-run) job_id."""
        result = parse_job_id("550e8400-e29b-41d4-a716-446655440000")
        assert result["project_id"] is None
        assert result["entity_name"] is None
        assert result["index"] is None
        assert result["is_dry_run"] is True

    def test_parse_invalid_format(self):
        """Parse invalid format returns empty result."""
        result = parse_job_id("invalid")
        assert result["project_id"] is None
        assert result["entity_name"] is None
        assert result["index"] is None
        assert result["is_dry_run"] is False
        assert result["raw"] == "invalid"

    def test_parse_empty_string(self):
        """Parse empty string returns empty result."""
        result = parse_job_id("")
        assert result["project_id"] is None
        assert result["is_dry_run"] is False

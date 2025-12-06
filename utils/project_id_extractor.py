"""Project ID extraction from job_id patterns.

This module provides utilities to extract project_id from various job_id formats
used by the crawler services.

Job ID Formats:
- Brand format: `proj_xyz-brand-0` → project_id = `proj_xyz`
- Competitor format: `proj_xyz-toyota-5` → project_id = `proj_xyz`
- Dry-run format: UUID (e.g., `550e8400-e29b-41d4-a716-446655440000`) → project_id = None
"""

from __future__ import annotations

import re
from typing import Optional

# UUID v4 pattern (dry-run tasks use UUID as job_id)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def extract_project_id(job_id: str) -> Optional[str]:
    """Extract project_id from a job_id string.

    The job_id follows specific patterns based on task type:
    - Brand/Competitor tasks: `{project_id}-{brand_or_competitor}-{index}`
    - Dry-run tasks: UUID format (no project association)

    Args:
        job_id: The job identifier string from crawler events.

    Returns:
        The extracted project_id, or None if:
        - job_id is a UUID (dry-run task)
        - job_id format is invalid/unrecognized
        - job_id is empty or None

    Examples:
        >>> extract_project_id("proj_abc123-brand-0")
        'proj_abc123'
        >>> extract_project_id("proj_xyz-toyota-5")
        'proj_xyz'
        >>> extract_project_id("my-project-competitor-10")
        'my-project'
        >>> extract_project_id("550e8400-e29b-41d4-a716-446655440000")
        None
        >>> extract_project_id("")
        None
    """
    if not job_id or not isinstance(job_id, str):
        return None

    job_id = job_id.strip()
    if not job_id:
        return None

    # Check if it's a UUID (dry-run task)
    if UUID_PATTERN.match(job_id):
        return None

    # Split by '-' and validate structure
    parts = job_id.split("-")

    # Need at least 3 parts: project_id_parts + brand/competitor + index
    if len(parts) < 3:
        return None

    # Last part must be a numeric index
    if not parts[-1].isdigit():
        return None

    # Project ID is everything except the last two parts (brand/competitor + index)
    project_id = "-".join(parts[:-2])

    # Validate project_id is not empty
    if not project_id:
        return None

    return project_id


def is_dry_run_job(job_id: str) -> bool:
    """Check if a job_id represents a dry-run task.

    Dry-run tasks use UUID format for job_id and have no associated project.

    Args:
        job_id: The job identifier string.

    Returns:
        True if the job_id is a UUID (dry-run), False otherwise.
    """
    if not job_id or not isinstance(job_id, str):
        return False

    return bool(UUID_PATTERN.match(job_id.strip()))


def parse_job_id(job_id: str) -> dict:
    """Parse a job_id into its components.

    Args:
        job_id: The job identifier string.

    Returns:
        Dictionary with parsed components:
        - project_id: str or None
        - entity_name: str or None (brand/competitor name)
        - index: int or None
        - is_dry_run: bool
        - raw: str (original job_id)
    """
    result = {
        "project_id": None,
        "entity_name": None,
        "index": None,
        "is_dry_run": False,
        "raw": job_id,
    }

    if not job_id or not isinstance(job_id, str):
        return result

    job_id = job_id.strip()
    if not job_id:
        return result

    # Check for dry-run (UUID)
    if UUID_PATTERN.match(job_id):
        result["is_dry_run"] = True
        return result

    parts = job_id.split("-")

    if len(parts) < 3:
        return result

    if not parts[-1].isdigit():
        return result

    result["index"] = int(parts[-1])
    result["entity_name"] = parts[-2]
    result["project_id"] = "-".join(parts[:-2])

    return result

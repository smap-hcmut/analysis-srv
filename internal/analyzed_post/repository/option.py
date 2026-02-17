"""Options structs for analyzed_post repository operations.

Convention: UseCase passes Options → Repository builds query from Options.
Repository returns model.AnalyzedPost (domain model), never raw DB types.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CreateOptions:
    """Options for creating an analyzed post."""

    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpsertOptions:
    """Options for upserting (insert or update) an analyzed post."""

    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GetOneOptions:
    """Options for getting a single analyzed post by filters."""

    id: Optional[str] = None
    post_id: Optional[str] = None
    project_id: Optional[str] = None


@dataclass
class ListOptions:
    """Options for listing analyzed posts (no pagination)."""

    project_id: Optional[str] = None
    status: Optional[str] = None
    platform: Optional[str] = None
    limit: int = 100
    order_by: str = "created_at DESC"


@dataclass
class UpdateStatusOptions:
    """Options for updating analyzed post status."""

    id: str = ""
    status: str = ""


@dataclass
class DeleteOptions:
    """Options for deleting analyzed posts."""

    id: Optional[str] = None
    project_id: Optional[str] = None


__all__ = [
    "CreateOptions",
    "UpsertOptions",
    "GetOneOptions",
    "ListOptions",
    "UpdateStatusOptions",
    "DeleteOptions",
]

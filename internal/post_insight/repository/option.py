from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union

from ..type import CreatePostInsightInput, UpdatePostInsightInput


@dataclass
class CreateOptions:
    data: Union[CreatePostInsightInput, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class UpsertOptions:
    data: Union[CreatePostInsightInput, UpdatePostInsightInput, Dict[str, Any]] = field(
        default_factory=dict
    )


@dataclass
class GetOneOptions:
    id: Optional[str] = None
    project_id: Optional[str] = None
    source_id: Optional[str] = None


@dataclass
class ListOptions:
    project_id: Optional[str] = None
    platform: Optional[str] = None
    overall_sentiment: Optional[str] = None
    risk_level: Optional[str] = None
    limit: int = 100
    order_by: str = "analyzed_at DESC"


@dataclass
class DeleteOptions:
    id: Optional[str] = None
    project_id: Optional[str] = None


__all__ = [
    "CreateOptions",
    "UpsertOptions",
    "GetOneOptions",
    "ListOptions",
    "DeleteOptions",
]

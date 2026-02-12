"""Types for Analyzed Post domain."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CreateAnalyzedPostInput:
    """Input for creating analyzed post."""
    
    data: dict[str, Any]


@dataclass
class UpdateAnalyzedPostInput:
    """Input for updating analyzed post."""
    
    data: dict[str, Any]


__all__ = ["CreateAnalyzedPostInput", "UpdateAnalyzedPostInput"]

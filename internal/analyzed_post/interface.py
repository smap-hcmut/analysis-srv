"""Interface for Analyzed Post use case.

Convention: Single Flat Interface, methods grouped by comments.
Methods accept dedicated Input/Output structs from types.py.
"""

from typing import Protocol, runtime_checkable

from internal.model import AnalyzedPost
from .type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput


@runtime_checkable
class IAnalyzedPostUseCase(Protocol):
    """Protocol for analyzed post operations."""

    # CRUD Operations
    async def create(self, input_data: CreateAnalyzedPostInput) -> AnalyzedPost:
        """Create a new analyzed post record."""
        ...

    async def update(self, post_id: str, input_data: UpdateAnalyzedPostInput) -> AnalyzedPost:
        """Update an existing analyzed post record."""
        ...


__all__ = ["IAnalyzedPostUseCase"]

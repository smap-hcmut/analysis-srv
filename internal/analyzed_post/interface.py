"""Interface for Analyzed Post use case."""

from typing import Protocol, runtime_checkable

from internal.model import AnalyzedPost
from .type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput


@runtime_checkable
class IAnalyzedPostUseCase(Protocol):
    """Protocol for analyzed post operations."""

    def create(self, input_data: CreateAnalyzedPostInput) -> AnalyzedPost:
        """Create a new analyzed post record.
        
        Args:
            input_data: Data for creating analyzed post
            
        Returns:
            Created AnalyzedPost instance
        """
        ...

    def update(self, post_id: str, input_data: UpdateAnalyzedPostInput) -> AnalyzedPost:
        """Update an existing analyzed post record.
        
        Args:
            post_id: ID of post to update
            input_data: Data for updating analyzed post
            
        Returns:
            Updated AnalyzedPost instance
        """
        ...


__all__ = ["IAnalyzedPostUseCase"]

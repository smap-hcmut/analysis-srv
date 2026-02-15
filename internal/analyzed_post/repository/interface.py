"""Repository interface for analyzed post domain."""

from typing import Protocol, runtime_checkable

from internal.model import AnalyzedPost


@runtime_checkable
class IAnalyzedPostRepository(Protocol):
    """Protocol for analyzed post repository."""

    def save(self, data: dict) -> AnalyzedPost:
        """Save analyzed post data.
        
        Args:
            data: Dictionary containing analyzed post fields
            
        Returns:
            Saved AnalyzedPost instance
        """
        ...

    def get_by_id(self, post_id: str) -> AnalyzedPost | None:
        """Get analyzed post by ID.
        
        Args:
            post_id: Post ID
            
        Returns:
            AnalyzedPost instance or None
        """
        ...


__all__ = ["IAnalyzedPostRepository"]

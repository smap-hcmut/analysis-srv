"""Repository interface for analyzed_post domain.

Convention: Interface Composition — group methods by entity.
Method naming: Verb + Entity (Create, GetOne, Detail, List, Upsert, UpdateStatus, Delete).
"""

from typing import List, Optional, Protocol, runtime_checkable

from internal.model import AnalyzedPost
from .option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    UpdateStatusOptions,
    DeleteOptions,
)


@runtime_checkable
class IAnalyzedPostRepository(Protocol):
    """Protocol for analyzed post repository.

    Rules:
    - All methods accept context implicitly (async).
    - Options pattern for all operations.
    - Return model.AnalyzedPost (domain model), never raw DB types.
    - Not found → return None (not raise error).
    """

    async def create(self, opt: CreateOptions) -> AnalyzedPost:
        """Insert a new analyzed post.

        Args:
            opt: Create options with data dict

        Returns:
            Created AnalyzedPost instance
        """
        ...

    async def upsert(self, opt: UpsertOptions) -> AnalyzedPost:
        """Insert or update an analyzed post.

        Args:
            opt: Upsert options with data dict

        Returns:
            Upserted AnalyzedPost instance
        """
        ...

    async def detail(self, id: str) -> Optional[AnalyzedPost]:
        """Get analyzed post by primary key.

        Args:
            id: Post ID (primary key)

        Returns:
            AnalyzedPost or None if not found
        """
        ...

    async def get_one(self, opt: GetOneOptions) -> Optional[AnalyzedPost]:
        """Get a single analyzed post by filters.

        Args:
            opt: Filter options

        Returns:
            AnalyzedPost or None if not found
        """
        ...

    async def list(self, opt: ListOptions) -> List[AnalyzedPost]:
        """List analyzed posts (no pagination).

        Args:
            opt: List options with filters

        Returns:
            List of AnalyzedPost instances
        """
        ...

    async def update_status(self, opt: UpdateStatusOptions) -> Optional[AnalyzedPost]:
        """Update analyzed post status.

        Args:
            opt: Update status options

        Returns:
            Updated AnalyzedPost or None if not found
        """
        ...

    async def delete(self, opt: DeleteOptions) -> bool:
        """Delete analyzed post(s).

        Args:
            opt: Delete options

        Returns:
            True if deleted, False otherwise
        """
        ...


__all__ = ["IAnalyzedPostRepository"]

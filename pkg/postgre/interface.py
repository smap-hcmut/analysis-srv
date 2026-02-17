"""Interface for PostgreSQL database operations."""

from typing import AsyncGenerator, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class IDatabase(Protocol):
    """Protocol for database operations.

    Implementations are safe for concurrent use.
    """

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session.

        Yields:
            AsyncSession instance
        """
        ...

    async def health_check(self) -> bool:
        """Check database connectivity.

        Returns:
            True if database is healthy, False otherwise
        """
        ...

    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        ...


__all__ = ["IDatabase"]

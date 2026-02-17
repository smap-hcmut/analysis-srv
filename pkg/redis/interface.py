"""Interface for Redis cache operations."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ICache(Protocol):
    """Protocol for cache operations.

    Implementations are safe for concurrent use.
    """

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        ...

    async def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete key."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key."""
        ...

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        ...

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        ...

    async def close(self) -> None:
        """Close Redis connection."""
        ...


__all__ = ["ICache"]

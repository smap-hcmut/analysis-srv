"""Cache interface - Abstract base class for caching operations."""

from abc import ABC, abstractmethod
from typing import Optional, Any


class ICache(ABC):
    """Interface for cache operations (Redis, Memcached, etc.)."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set a value in cache with optional TTL (seconds)."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all keys from cache."""
        pass

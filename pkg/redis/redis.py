import json
from typing import Optional, Protocol, runtime_checkable

import redis.asyncio as aioredis
from loguru import logger
from redis.asyncio import ConnectionPool

from .type import RedisConfig


@runtime_checkable
class ICache(Protocol):
    """Protocol for cache operations."""

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


class RedisCache:
    """Redis cache manager with async support.

    Uses redis-py async client for high-performance caching operations.
    Supports JSON serialization, TTL, and connection pooling.

    Example:
        >>> config = RedisConfig(
        ...     host="localhost",
        ...     port=6379,
        ...     db=0
        ... )
        >>> cache = RedisCache(config)
        >>>
        >>> await cache.set("user:123", {"name": "John"}, ttl=3600)
        >>> user = await cache.get("user:123")
        >>> print(user)  # {"name": "John"}
    """

    def __init__(self, config: RedisConfig):
        """Initialize Redis cache manager.

        Args:
            config: RedisConfig instance
        """
        self.config = config
        self.client = None
        self.pool = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Redis client with connection pool."""
        try:
            # Create connection pool
            pool_kwargs = {
                "host": self.config.host,
                "port": self.config.port,
                "db": self.config.db,
                "password": self.config.password,
                "username": self.config.username,
                "encoding": self.config.encoding,
                "decode_responses": self.config.decode_responses,
                "max_connections": self.config.max_connections,
                "socket_timeout": self.config.socket_timeout,
                "socket_connect_timeout": self.config.socket_connect_timeout,
                "socket_keepalive": self.config.socket_keepalive,
                "health_check_interval": self.config.health_check_interval,
            }

            if self.config.ssl:
                pool_kwargs["ssl"] = True
                pool_kwargs["ssl_cert_reqs"] = "required"

            self.pool = ConnectionPool(**pool_kwargs)

            # Create Redis client
            self.client = aioredis.Redis(connection_pool=self.pool)

            logger.info(f"Redis client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise

    async def get(self, key: str) -> Optional[str]:
        """Get value by key.

        Args:
            key: Cache key

        Returns:
            Value as string, or None if not found

        Example:
            >>> value = await cache.get("user:123")
            >>> if value:
            ...     user = json.loads(value)
        """
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None

    async def get_json(self, key: str) -> Optional[object]:
        """Get value by key and deserialize from JSON.

        Args:
            key: Cache key

        Returns:
            Deserialized value, or None if not found

        Example:
            >>> user = await cache.get_json("user:123")
            >>> print(user["name"])
        """
        value = await self.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL.

        Args:
            key: Cache key
            value: Value to store (will be JSON serialized if not string)
            ttl: Time-to-live in seconds (optional)

        Returns:
            True if successful, False otherwise

        Example:
            >>> await cache.set("user:123", {"name": "John"}, ttl=3600)
            >>> await cache.set("counter", "42", ttl=60)
        """
        try:
            # Serialize to JSON if not string
            if not isinstance(value, str):
                value = json.dumps(value)

            if ttl:
                return await self.client.setex(key, ttl, value)
            else:
                return await self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise

        Example:
            >>> await cache.delete("user:123")
        """
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise

        Example:
            >>> if await cache.exists("user:123"):
            ...     print("User exists in cache")
        """
        try:
            result = await self.client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error for key '{key}': {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            True if successful, False otherwise

        Example:
            >>> await cache.expire("user:123", 3600)
        """
        try:
            return await self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key '{key}': {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key.

        Args:
            key: Cache key

        Returns:
            Remaining TTL in seconds, -1 if no expiry, -2 if key doesn't exist

        Example:
            >>> remaining = await cache.ttl("user:123")
            >>> print(f"Expires in {remaining} seconds")
        """
        try:
            return await self.client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL error for key '{key}': {e}")
            return -2

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment key by amount.

        Args:
            key: Cache key
            amount: Amount to increment (default: 1)

        Returns:
            New value after increment, or None on error

        Example:
            >>> count = await cache.incr("page_views")
            >>> print(f"Page views: {count}")
        """
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR error for key '{key}': {e}")
            return None

    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement key by amount.

        Args:
            key: Cache key
            amount: Amount to decrement (default: 1)

        Returns:
            New value after decrement, or None on error

        Example:
            >>> remaining = await cache.decr("rate_limit:user:123")
        """
        try:
            return await self.client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Redis DECR error for key '{key}': {e}")
            return None

    async def mget(self, keys: list[str]) -> list[Optional[str]]:
        """Get multiple values by keys.

        Args:
            keys: List of cache keys

        Returns:
            List of values (None for missing keys)

        Example:
            >>> values = await cache.mget(["user:1", "user:2", "user:3"])
        """
        try:
            return await self.client.mget(keys)
        except Exception as e:
            logger.error(f"Redis MGET error: {e}")
            return [None] * len(keys)

    async def mset(self, mapping: dict[str, object]) -> bool:
        """Set multiple key-value pairs.

        Args:
            mapping: Dictionary of key-value pairs

        Returns:
            True if successful, False otherwise

        Example:
            >>> await cache.mset({
            ...     "user:1": {"name": "Alice"},
            ...     "user:2": {"name": "Bob"}
            ... })
        """
        try:
            # Serialize values to JSON if needed
            serialized = {}
            for key, value in mapping.items():
                if not isinstance(value, str):
                    serialized[key] = json.dumps(value)
                else:
                    serialized[key] = value

            return await self.client.mset(serialized)
        except Exception as e:
            logger.error(f"Redis MSET error: {e}")
            return False

    async def health_check(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is healthy, False otherwise

        Example:
            >>> is_healthy = await cache.health_check()
            >>> print(f"Redis healthy: {is_healthy}")
        """
        try:
            return await self.client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection and cleanup resources.

        Example:
            >>> await cache.close()
        """
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")

        if self.pool:
            await self.pool.disconnect()
            logger.info("Redis connection pool closed")

    async def get_info(self) -> dict:
        """Get Redis server info.

        Returns:
            Dictionary with Redis server information

        Example:
            >>> info = await cache.get_info()
            >>> print(f"Redis version: {info.get('redis_version')}")
        """
        try:
            return await self.client.info()
        except Exception as e:
            logger.error(f"Redis INFO error: {e}")
            return {}


__all__ = [
    "ICache",
    "RedisCache",
]

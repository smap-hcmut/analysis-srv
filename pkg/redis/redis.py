import asyncio
import json
import time
from typing import Awaitable, Callable, Optional

import redis.asyncio as aioredis
from loguru import logger
from redis.asyncio import ConnectionPool

from .interface import ICache
from .type import RedisConfig


class RedisCache:
    """Redis cache manager with async support.

    Uses redis-py async client for high-performance caching operations.
    Supports JSON serialization, TTL, and connection pooling.
    """

    _RETRY_ATTEMPTS = 3
    _RETRY_DELAYS_SECONDS = (0.05, 0.15, 0.3)
    _ERROR_LOG_COOLDOWN_SECONDS = 60

    def __init__(self, config: RedisConfig):
        """Initialize Redis cache manager.

        Args:
            config: RedisConfig instance
        """
        self.config = config
        self.client = None
        self.pool = None
        self._error_throttle: dict[str, float] = {}
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

        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise

    async def get(self, key: str) -> Optional[str]:
        """Get value by key.

        Args:
            key: Cache key

        Returns:
            Value as string, or None if not found
        """
        return await self._execute_with_retry("GET", key, lambda: self.client.get(key), None)

    async def get_json(self, key: str) -> Optional[object]:
        """Get value by key and deserialize from JSON.

        Args:
            key: Cache key

        Returns:
            Deserialized value, or None if not found
        """
        value = await self.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            self._log_error("JSON", key, e, retrying=False, is_transient=False)
            return None

    async def set(self, key: str, value: object, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL.

        Args:
            key: Cache key
            value: Value to store (will be JSON serialized if not string)
            ttl: Time-to-live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """

        async def operation() -> bool:
            payload = json.dumps(value) if not isinstance(value, str) else value
            if ttl:
                return await self.client.setex(key, ttl, payload)
            return await self.client.set(key, payload)

        return await self._execute_with_retry("SET", key, operation, False)

    async def delete(self, key: str) -> bool:
        """Delete key.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise
        """
        async def operation() -> bool:
            return self._to_bool(await self.client.delete(key))
        return await self._execute_with_retry(
            "DELETE",
            key,
            operation,
            False,
        )

    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        async def operation() -> bool:
            return self._to_bool(await self.client.exists(key))
        return await self._execute_with_retry(
            "EXISTS",
            key,
            operation,
            False,
        )

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            True if successful, False otherwise
        """
        async def operation() -> bool:
            return self._to_bool(await self.client.expire(key, ttl))
        return await self._execute_with_retry(
            "EXPIRE",
            key,
            operation,
            False,
        )

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key.

        Args:
            key: Cache key

        Returns:
            Remaining TTL in seconds, -1 if no expiry, -2 if key doesn't exist
        """
        return await self._execute_with_retry("TTL", key, lambda: self.client.ttl(key), -2)

    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment key by amount.

        Args:
            key: Cache key
            amount: Amount to increment (default: 1)

        Returns:
            New value after increment, or None on error
        """
        return await self._execute_with_retry("INCR", key, lambda: self.client.incrby(key, amount), None)

    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement key by amount.

        Args:
            key: Cache key
            amount: Amount to decrement (default: 1)

        Returns:
            New value after decrement, or None on error
        """
        return await self._execute_with_retry("DECR", key, lambda: self.client.decrby(key, amount), None)

    async def mget(self, keys: list[str]) -> list[Optional[str]]:
        """Get multiple values by keys.

        Args:
            keys: List of cache keys

        Returns:
            List of values (None for missing keys)
        """
        key = ",".join(keys[:5]) if keys else "<empty>"
        return await self._execute_with_retry("MGET", key, lambda: self.client.mget(keys), [None] * len(keys))

    async def mset(self, mapping: dict[str, object]) -> bool:
        """Set multiple key-value pairs.

        Args:
            mapping: Dictionary of key-value pairs

        Returns:
            True if successful, False otherwise
        """
        first_key = next(iter(mapping.keys()), "<empty>")

        async def operation() -> bool:
            serialized = {}
            for item_key, item_value in mapping.items():
                serialized[item_key] = json.dumps(item_value) if not isinstance(item_value, str) else item_value
            return await self.client.mset(serialized)

        return await self._execute_with_retry("MSET", first_key, operation, False)

    async def health_check(self) -> bool:
        """Check Redis connectivity.

        Returns:
            True if Redis is healthy, False otherwise
        """
        return bool(
            await self._execute_with_retry(
                "PING",
                "server",
                self.client.ping,
                False,
            )
        )

    async def close(self) -> None:
        """Close Redis connection and cleanup resources."""
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
        return await self._execute_with_retry("INFO", "server", self.client.info, {})

    async def _execute_with_retry(
        self,
        operation: str,
        key: str,
        fn: Callable[[], Awaitable],
        fallback,
    ):
        last_error: Exception | None = None
        for attempt in range(1, self._RETRY_ATTEMPTS + 1):
            try:
                return await fn()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_error = exc
                retriable = self._is_retriable_error(exc)
                if not retriable or attempt == self._RETRY_ATTEMPTS:
                    self._log_error(operation, key, exc, retrying=False, is_transient=retriable)
                    return fallback
                self._log_error(operation, key, exc, retrying=True, is_transient=True)
                await asyncio.sleep(self._RETRY_DELAYS_SECONDS[attempt - 1])

        if last_error is not None:
            self._log_error(operation, key, last_error, retrying=False, is_transient=self._is_retriable_error(last_error))
        return fallback

    def _to_bool(self, value) -> bool:
        return bool(value)

    def _is_retriable_error(self, error: Exception) -> bool:
        message = str(error).lower()
        transient_signals = (
            "loading redis is loading the dataset in memory",
            "connect: connection refused",
            "connection refused",
            "connection timed out",
            "timeout",
            "read: connection reset",
            "connection reset",
            "temporary failure",
            "i/o timeout",
            "dial tcp",
        )
        return any(signal in message for signal in transient_signals)

    def _log_error(self, operation: str, key: str, error: Exception, *, retrying: bool, is_transient: bool) -> None:
        event_key = f"{operation}:{key}"
        now = time.time()
        if now < self._error_throttle.get(event_key, 0.0):
            return

        self._error_throttle[event_key] = now + self._ERROR_LOG_COOLDOWN_SECONDS
        if retrying or is_transient:
            logger.warning(f"Redis {operation} retrying for key '{key}': {error}")
        else:
            logger.error(f"Redis {operation} error for key '{key}': {error}")


__all__ = [
    "RedisCache",
]

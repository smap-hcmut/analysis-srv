from dataclasses import dataclass
from typing import Optional

from .constant import *


@dataclass
class RedisConfig:
    """Configuration for Redis cache.

    Attributes:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)
        password: Redis password (optional)
        username: Redis username (optional, Redis 6+)
        ssl: Enable SSL/TLS (default: False)
        encoding: String encoding (default: utf-8)
        decode_responses: Decode responses to strings (default: True)
        max_connections: Max connections in pool (default: 50)
        socket_timeout: Socket timeout in seconds (default: 5)
        socket_connect_timeout: Socket connect timeout (default: 5)
        socket_keepalive: Enable TCP keepalive (default: True)
        health_check_interval: Health check interval in seconds (default: 30)
    """

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    db: int = DEFAULT_DB
    password: Optional[str] = None
    username: Optional[str] = None
    ssl: bool = DEFAULT_SSL
    encoding: str = DEFAULT_ENCODING
    decode_responses: bool = DEFAULT_DECODE_RESPONSES
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    socket_timeout: int = DEFAULT_SOCKET_TIMEOUT
    socket_connect_timeout: int = DEFAULT_SOCKET_CONNECT_TIMEOUT
    socket_keepalive: bool = DEFAULT_SOCKET_KEEPALIVE
    health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL

    def __post_init__(self):
        """Validate configuration."""
        if not self.host:
            raise ValueError(ERROR_HOST_EMPTY)
        if self.port <= 0 or self.port > 65535:
            raise ValueError(ERROR_INVALID_PORT)
        if self.db < 0:
            raise ValueError(ERROR_INVALID_DB)
        if self.max_connections <= 0:
            raise ValueError(ERROR_INVALID_MAX_CONNECTIONS)
        if self.socket_timeout <= 0:
            raise ValueError(ERROR_INVALID_SOCKET_TIMEOUT)


__all__ = [
    "RedisConfig",
]

from dataclasses import dataclass

from .constant import *


@dataclass
class PostgresConfig:
    """Configuration for PostgreSQL database.

    Attributes:
        database_url: PostgreSQL connection URL (asyncpg format)
        schema: Schema name to use (for multi-tenant isolation)
        pool_size: Connection pool size (default: 20)
        max_overflow: Max overflow connections (default: 10)
        pool_recycle: Recycle connections after N seconds (default: 3600)
        pool_pre_ping: Verify connections before use (default: True)
        echo: Log SQL queries (default: False)
        echo_pool: Log pool events (default: False)
    """

    database_url: str
    schema: str = DEFAULT_SCHEMA
    pool_size: int = DEFAULT_POOL_SIZE
    max_overflow: int = DEFAULT_MAX_OVERFLOW
    pool_recycle: int = DEFAULT_POOL_RECYCLE
    pool_pre_ping: bool = DEFAULT_POOL_PRE_PING
    echo: bool = DEFAULT_ECHO
    echo_pool: bool = DEFAULT_ECHO_POOL

    def __post_init__(self):
        """Validate configuration."""
        if not self.database_url:
            raise ValueError(ERROR_DATABASE_URL_EMPTY)
        if not self.database_url.startswith(
            ("postgresql+asyncpg://", "postgresql://", "postgres://")
        ):
            raise ValueError(ERROR_INVALID_DATABASE_URL)
        if self.pool_size <= 0:
            raise ValueError(ERROR_POOL_SIZE_POSITIVE)
        if self.max_overflow < 0:
            raise ValueError(ERROR_MAX_OVERFLOW_NON_NEGATIVE)
        if self.pool_recycle <= 0:
            raise ValueError(ERROR_POOL_RECYCLE_POSITIVE)
        if not self.schema or not self.schema.strip():
            raise ValueError(ERROR_SCHEMA_EMPTY)


__all__ = [
    "PostgresConfig",
]

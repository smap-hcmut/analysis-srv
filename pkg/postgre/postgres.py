from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .interface import IDatabase
from .type import PostgresConfig
from .constant import *


class PostgresDatabase:
    """PostgreSQL database manager with async support.

    Uses SQLAlchemy async with asyncpg driver for high-performance
    async database operations.
    """

    def __init__(self, config: PostgresConfig):
        """Initialize PostgreSQL database manager.

        Args:
            config: PostgresConfig instance
        """
        self.config = config
        self.engine = None
        self.session_factory = None
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """Initialize async database engine and session factory."""
        try:
            # Ensure URL uses asyncpg driver
            url = self.config.database_url
            if url.startswith("postgresql://") or url.startswith("postgres://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)

            # Create async engine with connection pooling
            engine_kwargs = {
                "echo": self.config.echo,
                "echo_pool": self.config.echo_pool,
                "pool_pre_ping": self.config.pool_pre_ping,
                "pool_recycle": self.config.pool_recycle,
            }

            # Use NullPool if echo is enabled (debug mode)
            if self.config.echo:
                engine_kwargs["poolclass"] = NullPool
            else:
                engine_kwargs["pool_size"] = self.config.pool_size
                engine_kwargs["max_overflow"] = self.config.max_overflow

            self.engine = create_async_engine(url, **engine_kwargs)

            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,  # Keep objects accessible after commit
                autoflush=True,
                autocommit=False,
            )

            logger.info(f"PostgreSQL engine initialized")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL engine: {e}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with automatic cleanup.

        Yields:
            AsyncSession instance

        Raises:
            RuntimeError: If database not initialized
        """
        if not self.session_factory:
            raise RuntimeError(ERROR_DATABASE_NOT_INITIALIZED)

        async with self.session_factory() as session:
            try:
                # Set search_path to use the configured schema
                if self.config.schema and self.config.schema != DEFAULT_SCHEMA:
                    await session.execute(
                        text(
                            f"SET search_path TO {self.config.schema}, {DEFAULT_SCHEMA}"
                        )
                    )
                yield session
            except Exception as e:
                logger.error(f"Database session error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        """Check database connectivity.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close database engine and cleanup resources."""
        if self.engine:
            await self.engine.dispose()
            logger.info("PostgreSQL engine closed")

    async def execute_raw(self, query: str, params: dict = None) -> any:
        """Execute raw SQL query.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            Query result
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()
            return result

    async def get_pool_status(self) -> dict:
        """Get connection pool status.

        Returns:
            Dictionary with pool statistics
        """
        if not self.engine or not hasattr(self.engine.pool, "size"):
            return {"error": "Pool not available"}

        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
        }


__all__ = [
    "PostgresDatabase",
]

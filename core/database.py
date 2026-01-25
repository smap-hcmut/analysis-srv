"""Async database configuration and session management for API service."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings
from core.logger import logger


class DatabaseManager:
    """Async database manager for API service."""
    
    def __init__(self):
        """Initialize async database engine and session factory."""
        self.engine = None
        self.async_session_factory = None
        
    def initialize(self):
        """Initialize async database engine and session factory."""
        try:
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                settings.database_url,
                echo=settings.debug,  # Log SQL queries in debug mode
                poolclass=NullPool if settings.debug else None,  # Disable pooling in debug
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,   # Recycle connections after 1 hour
            )
            
            # Create session factory
            self.async_session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,  # Keep objects accessible after commit
                autoflush=True,
                autocommit=False,
            )
            
            logger.info("Async database engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize async database engine: {e}")
            raise
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session."""
        if not self.async_session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
            
        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Database session error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.async_session_factory() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def close(self):
        """Close database engine."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database engine closed")


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database session."""
    async for session in db_manager.get_session():
        yield session


async def init_database():
    """Initialize database on startup."""
    db_manager.initialize()


async def close_database():
    """Close database on shutdown."""
    await db_manager.close()
"""Factory function for creating analyzed post repository."""

from typing import Optional

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from .postgre.repository import AnalyzedPostRepository


def New(db: PostgresDatabase, logger: Optional[Logger] = None) -> AnalyzedPostRepository:
    """Create a new analyzed post repository instance.
    
    Args:
        db: PostgresDatabase instance (will use get_session() internally)
        logger: Logger instance (optional)
        
    Returns:
        AnalyzedPostRepository instance
        
    Raises:
        ValueError: If db is invalid
    """
    if db is None:
        raise ValueError("db cannot be None")
    
    return AnalyzedPostRepository(db, logger)


__all__ = ["New"]

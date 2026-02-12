"""Factory function for creating analyzed post repository."""

from typing import Optional
from sqlalchemy.orm import Session

from pkg.logger.logger import Logger
from .postgre.repository import AnalyzedPostRepository


def New(db: Session, logger: Optional[Logger] = None) -> AnalyzedPostRepository:
    """Create a new analyzed post repository instance.
    
    Args:
        db: SQLAlchemy database session
        logger: Logger instance (optional)
        
    Returns:
        AnalyzedPostRepository instance
        
    Raises:
        ValueError: If db is invalid
    """
    if db is None:
        raise ValueError("db session cannot be None")
    
    return AnalyzedPostRepository(db, logger)


__all__ = ["New"]

"""Factory function for creating analyzed post repository."""

from typing import Optional

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from .postgre.analyzed_post import AnalyzedPostPostgresRepository


def New(
    db: PostgresDatabase,
    logger: Optional[Logger] = None,
) -> AnalyzedPostPostgresRepository:
    """Create a new analyzed post repository instance.

    Args:
        db: PostgresDatabase instance
        logger: Logger instance (optional)

    Returns:
        AnalyzedPostPostgresRepository instance
    """
    if db is None:
        raise ValueError("db cannot be None")

    return AnalyzedPostPostgresRepository(db=db, logger=logger)


__all__ = ["New"]

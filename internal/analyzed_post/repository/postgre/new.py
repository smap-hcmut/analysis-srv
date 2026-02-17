"""Factory for PostgreSQL analyzed post repository."""

from typing import Optional

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from .analyzed_post import AnalyzedPostPostgresRepository


def New(
    db: PostgresDatabase,
    logger: Optional[Logger] = None,
) -> AnalyzedPostPostgresRepository:
    """Create a new analyzed post PostgreSQL repository.

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

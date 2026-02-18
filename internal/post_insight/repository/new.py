from typing import Optional

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from .postgre.post_insight import PostInsightPostgresRepository


def New(
    db: PostgresDatabase,
    logger: Optional[Logger] = None,
) -> PostInsightPostgresRepository:
    return PostInsightPostgresRepository(db=db, logger=logger)


__all__ = ["New"]

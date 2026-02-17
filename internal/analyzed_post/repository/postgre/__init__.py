"""PostgreSQL implementation of analyzed_post repository."""

from .analyzed_post import AnalyzedPostPostgresRepository
from .new import New

__all__ = [
    "AnalyzedPostPostgresRepository",
    "New",
]

"""Query builders for analyzed_post repository.

Convention: Pure query building — returns SQLAlchemy select statements.
No DB execution, no domain mapping.
"""

from sqlalchemy import select, delete as sql_delete

from internal.model import AnalyzedPost
from ..option import GetOneOptions, ListOptions, DeleteOptions


def build_get_one_query(opt: GetOneOptions):
    """Build query for getting a single analyzed post.

    Args:
        opt: Filter options (all non-None fields are AND-ed)

    Returns:
        SQLAlchemy select statement
    """
    stmt = select(AnalyzedPost)

    if opt.id:
        stmt = stmt.where(AnalyzedPost.id == opt.id)
    if opt.post_id:
        stmt = stmt.where(AnalyzedPost.id == opt.post_id)
    if opt.project_id:
        stmt = stmt.where(AnalyzedPost.project_id == opt.project_id)

    stmt = stmt.limit(1)
    return stmt


def build_list_query(opt: ListOptions):
    """Build query for listing analyzed posts.

    Args:
        opt: List options with filters

    Returns:
        SQLAlchemy select statement
    """
    stmt = select(AnalyzedPost)

    if opt.project_id:
        stmt = stmt.where(AnalyzedPost.project_id == opt.project_id)
    if opt.status:
        stmt = stmt.where(AnalyzedPost.status == opt.status)
    if opt.platform:
        stmt = stmt.where(AnalyzedPost.platform == opt.platform)

    # Ordering
    if opt.order_by:
        stmt = stmt.order_by(AnalyzedPost.created_at.desc())

    # Limit
    if opt.limit > 0:
        stmt = stmt.limit(opt.limit)

    return stmt


def build_delete_query(opt: DeleteOptions):
    """Build query for deleting analyzed posts.

    Args:
        opt: Delete options

    Returns:
        SQLAlchemy delete statement
    """
    stmt = sql_delete(AnalyzedPost)

    if opt.id:
        stmt = stmt.where(AnalyzedPost.id == opt.id)
    if opt.project_id:
        stmt = stmt.where(AnalyzedPost.project_id == opt.project_id)

    return stmt


__all__ = [
    "build_get_one_query",
    "build_list_query",
    "build_delete_query",
]

from sqlalchemy import select, delete as sql_delete

from internal.model.post_insight import PostInsight
from ..option import GetOneOptions, ListOptions, DeleteOptions


def build_get_one_query(opt: GetOneOptions):
    stmt = select(PostInsight)

    if opt.id:
        stmt = stmt.where(PostInsight.id == opt.id)
    if opt.project_id:
        stmt = stmt.where(PostInsight.project_id == opt.project_id)
    if opt.source_id:
        stmt = stmt.where(PostInsight.source_id == opt.source_id)

    stmt = stmt.limit(1)
    return stmt


def build_list_query(opt: ListOptions):
    stmt = select(PostInsight)

    if opt.project_id:
        stmt = stmt.where(PostInsight.project_id == opt.project_id)
    if opt.platform:
        stmt = stmt.where(PostInsight.platform == opt.platform)
    if opt.overall_sentiment:
        stmt = stmt.where(PostInsight.overall_sentiment == opt.overall_sentiment)
    if opt.risk_level:
        stmt = stmt.where(PostInsight.risk_level == opt.risk_level)

    # Ordering
    if opt.order_by:
        stmt = stmt.order_by(PostInsight.analyzed_at.desc())

    # Limit
    if opt.limit > 0:
        stmt = stmt.limit(opt.limit)

    return stmt


def build_delete_query(opt: DeleteOptions):
    stmt = sql_delete(PostInsight)

    if opt.id:
        stmt = stmt.where(PostInsight.id == opt.id)
    if opt.project_id:
        stmt = stmt.where(PostInsight.project_id == opt.project_id)

    return stmt


__all__ = [
    "build_get_one_query",
    "build_list_query",
    "build_delete_query",
]

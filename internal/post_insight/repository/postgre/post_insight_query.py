from sqlalchemy import select, delete as sql_delete, asc, desc

from internal.model.post_insight import PostInsight
from ..option import GetOneOptions, ListOptions, DeleteOptions

# Map order_by string tokens → (column, direction_fn)
_ORDER_BY_COLUMNS = {
    "analyzed_at": PostInsight.analyzed_at,
    "created_at": PostInsight.created_at,
    "updated_at": PostInsight.updated_at,
    "content_created_at": PostInsight.content_created_at,
    "risk_score": PostInsight.risk_score,
    "impact_score": PostInsight.impact_score,
    "overall_sentiment_score": PostInsight.overall_sentiment_score,
}


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

    # Ordering — parse "column_name [ASC|DESC]" string
    if opt.order_by:
        parts = opt.order_by.strip().split()
        col_name = parts[0].lower()
        direction = parts[1].upper() if len(parts) > 1 else "DESC"
        col = _ORDER_BY_COLUMNS.get(col_name)
        if col is not None:
            stmt = stmt.order_by(desc(col) if direction == "DESC" else asc(col))
        else:
            # Unrecognised column — fall back to analyzed_at DESC
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

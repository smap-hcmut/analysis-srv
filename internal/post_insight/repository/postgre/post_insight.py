from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from internal.model.post_insight import PostInsight
from ..interface import IPostInsightRepository
from ..option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    DeleteOptions,
)
from ..errors import (
    ErrFailedToCreate,
    ErrFailedToGet,
    ErrFailedToDelete,
    ErrFailedToUpsert,
)
from .post_insight_query import (
    build_get_one_query,
    build_list_query,
    build_delete_query,
)
from .helpers import transform_to_post_insight


class PostInsightPostgresRepository(IPostInsightRepository):

    def __init__(self, db: PostgresDatabase, logger: Optional[Logger] = None):
        self.db = db
        self.logger = logger

    async def create(self, opt: CreateOptions) -> PostInsight:
        transformed = transform_to_post_insight(opt.data)

        try:
            async with self.db.get_session() as session:
                record = PostInsight(**transformed)
                session.add(record)
                await session.commit()
                await session.refresh(record)

                return record

        except SQLAlchemyError as exc:
            self.logger.error(
                f"internal.post_insight.repository.postgre.post_insight.create: {exc}"
            )
            raise ErrFailedToCreate(exc) from exc

    async def upsert(self, opt: UpsertOptions) -> PostInsight:
        transformed = transform_to_post_insight(opt.data)

        id_ = transformed.get("id")
        project_id = transformed.get("project_id")
        source_id = transformed.get("source_id")

        try:
            async with self.db.get_session() as session:
                existing = None

                if id_:
                    stmt = select(PostInsight).where(PostInsight.id == id_)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                if not existing and project_id and source_id:
                    stmt = select(PostInsight).where(
                        PostInsight.project_id == project_id,
                        PostInsight.source_id == source_id,
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                if existing:
                    for key, value in transformed.items():
                        if key != "id":
                            setattr(existing, key, value)
                    record = existing
                else:
                    if not project_id:
                        self.logger.error(
                            "internal.post_insight.repository.postgre.post_insight.upsert: project_id is required for insertion"
                        )
                        raise ErrFailedToUpsert("project_id is required for insertion")

                    record = PostInsight(**transformed)
                    session.add(record)

                await session.commit()
                await session.refresh(record)

                return record

        except SQLAlchemyError as exc:
            self.logger.error(
                f"internal.post_insight.repository.postgre.post_insight.upsert: {exc}"
            )
            raise ErrFailedToUpsert(exc) from exc

    async def detail(self, id: str) -> Optional[PostInsight]:
        try:
            async with self.db.get_session() as session:
                stmt = select(PostInsight).where(PostInsight.id == id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            self.logger.error(
                f"internal.post_insight.repository.postgre.post_insight.detail: {exc}"
            )
            raise ErrFailedToGet(exc) from exc

    async def get_one(self, opt: GetOneOptions) -> Optional[PostInsight]:
        try:
            async with self.db.get_session() as session:
                stmt = build_get_one_query(opt)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            self.logger.error(
                f"internal.post_insight.repository.postgre.post_insight.get_one: {exc}"
            )
            raise ErrFailedToGet(exc) from exc

    async def list(self, opt: ListOptions) -> List[PostInsight]:
        try:
            async with self.db.get_session() as session:
                stmt = build_list_query(opt)
                result = await session.execute(stmt)
                return list(result.scalars().all())

        except SQLAlchemyError as exc:
            self.logger.error(
                f"internal.post_insight.repository.postgre.post_insight.list: {exc}"
            )
            raise ErrFailedToGet(exc) from exc

    async def delete(self, opt: DeleteOptions) -> bool:
        try:
            async with self.db.get_session() as session:
                stmt = build_delete_query(opt)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0

        except SQLAlchemyError as exc:
            self.logger.error(
                f"internal.post_insight.repository.postgre.post_insight.delete: {exc}"
            )
            raise ErrFailedToDelete(exc) from exc


__all__ = ["PostInsightPostgresRepository"]

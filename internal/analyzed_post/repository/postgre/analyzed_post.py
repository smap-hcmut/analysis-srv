"""PostgreSQL repository for analyzed_post entity.

Convention: Coordinator file — calls query builders, executes, maps to domain model.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from pkg.logger.logger import Logger
from pkg.postgre.postgres import PostgresDatabase
from internal.model import AnalyzedPost
from ..interface import IAnalyzedPostRepository
from ..option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    UpdateStatusOptions,
    DeleteOptions,
)
from ..errors import (
    ErrFailedToCreate,
    ErrFailedToGet,
    ErrFailedToUpdate,
    ErrFailedToDelete,
    ErrFailedToUpsert,
    ErrInvalidData,
)
from .analyzed_post_query import (
    build_get_one_query,
    build_list_query,
    build_delete_query,
)
from .helpers import sanitize_data, sanitize_project_id


class AnalyzedPostPostgresRepository(IAnalyzedPostRepository):
    """PostgreSQL implementation of analyzed post repository."""

    def __init__(self, db: PostgresDatabase, logger: Optional[Logger] = None) -> None:
        self.db = db
        self.logger = logger

    async def create(self, opt: CreateOptions) -> AnalyzedPost:
        """Insert a new analyzed post."""
        data = sanitize_data(opt.data)
        sanitize_project_id(data)

        post_id = data.get("id")
        if not post_id:
            raise ErrInvalidData("data must contain 'id' field")

        try:
            async with self.db.get_session() as session:
                post = AnalyzedPost(**data)
                session.add(post)
                await session.commit()
                await session.refresh(post)

                if self.logger:
                    self.logger.debug(f"[Repository] Created AnalyzedPost: id={post_id}")
                return post

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] create: {exc}")
            raise ErrFailedToCreate(f"create: {exc}") from exc

    async def upsert(self, opt: UpsertOptions) -> AnalyzedPost:
        """Insert or update an analyzed post."""
        data = sanitize_data(opt.data)
        sanitize_project_id(data)

        post_id = data.get("id")
        if not post_id:
            raise ErrInvalidData("data must contain 'id' field")

        try:
            async with self.db.get_session() as session:
                stmt = select(AnalyzedPost).where(AnalyzedPost.id == post_id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing is None:
                    post = AnalyzedPost(**data)
                    session.add(post)
                    if self.logger:
                        self.logger.debug(f"[Repository] Upsert (insert): id={post_id}")
                else:
                    post = existing
                    for key, value in data.items():
                        if hasattr(post, key):
                            setattr(post, key, value)
                    if self.logger:
                        self.logger.debug(f"[Repository] Upsert (update): id={post_id}")

                await session.commit()
                await session.refresh(post)
                return post

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] upsert: {exc}")
            raise ErrFailedToUpsert(f"upsert: {exc}") from exc

    async def detail(self, id: str) -> Optional[AnalyzedPost]:
        """Get by primary key. Returns None if not found."""
        try:
            async with self.db.get_session() as session:
                stmt = select(AnalyzedPost).where(AnalyzedPost.id == id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] detail: {exc}")
            raise ErrFailedToGet(f"detail: {exc}") from exc

    async def get_one(self, opt: GetOneOptions) -> Optional[AnalyzedPost]:
        """Get single post by filters. Returns None if not found."""
        try:
            async with self.db.get_session() as session:
                stmt = build_get_one_query(opt)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] get_one: {exc}")
            raise ErrFailedToGet(f"get_one: {exc}") from exc

    async def list(self, opt: ListOptions) -> List[AnalyzedPost]:
        """List posts by filters."""
        try:
            async with self.db.get_session() as session:
                stmt = build_list_query(opt)
                result = await session.execute(stmt)
                return list(result.scalars().all())

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] list: {exc}")
            raise ErrFailedToGet(f"list: {exc}") from exc

    async def update_status(self, opt: UpdateStatusOptions) -> Optional[AnalyzedPost]:
        """Update post status by ID."""
        if not opt.id or not opt.status:
            raise ErrInvalidData("id and status are required")

        try:
            async with self.db.get_session() as session:
                stmt = select(AnalyzedPost).where(AnalyzedPost.id == opt.id)
                result = await session.execute(stmt)
                post = result.scalar_one_or_none()

                if post is None:
                    return None

                post.status = opt.status
                await session.commit()
                await session.refresh(post)

                if self.logger:
                    self.logger.debug(
                        f"[Repository] update_status: id={opt.id}, status={opt.status}"
                    )
                return post

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] update_status: {exc}")
            raise ErrFailedToUpdate(f"update_status: {exc}") from exc

    async def delete(self, opt: DeleteOptions) -> bool:
        """Delete post(s) by filters."""
        try:
            async with self.db.get_session() as session:
                stmt = build_delete_query(opt)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0

        except SQLAlchemyError as exc:
            if self.logger:
                self.logger.error(f"[Repository] delete: {exc}")
            raise ErrFailedToDelete(f"delete: {exc}") from exc


__all__ = ["AnalyzedPostPostgresRepository"]

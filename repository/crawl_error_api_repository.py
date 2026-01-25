"""Async repository for crawl errors (API service)."""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.logger import logger
from interfaces.analytics_api_repository import ErrorFilters
from models.database import CrawlError
from models.schemas.base import PaginationParams


class CrawlErrorApiRepository:
    """Async repository for crawl error operations in API service."""

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db

    async def get_errors(
        self,
        filters: ErrorFilters,
        pagination: PaginationParams,
    ) -> Tuple[List[CrawlError], int]:
        """Get paginated crawl errors with filtering."""
        try:
            # Build base query
            conditions = [CrawlError.project_id == filters.project_id]

            # Apply filters
            if filters.job_id:
                conditions.append(CrawlError.job_id == filters.job_id)
            if filters.error_code:
                conditions.append(CrawlError.error_code == filters.error_code)
            if filters.from_date:
                conditions.append(CrawlError.created_at >= filters.from_date)
            if filters.to_date:
                conditions.append(CrawlError.created_at <= filters.to_date)

            # Get total count
            count_query = select(func.count(CrawlError.id)).where(and_(*conditions))
            total_count = (await self.db.execute(count_query)).scalar() or 0

            # Build main query with pagination
            query = (
                select(CrawlError)
                .where(and_(*conditions))
                .order_by(desc(CrawlError.created_at))
                .offset((pagination.page - 1) * pagination.page_size)
                .limit(pagination.page_size)
            )

            # Execute query
            result = await self.db.execute(query)
            errors = list(result.scalars().all())

            logger.debug(
                f"Retrieved {len(errors)} crawl errors out of {total_count} total "
                f"(page {pagination.page}, size {pagination.page_size})"
            )

            return errors, total_count

        except Exception as e:
            logger.error(f"Error retrieving crawl errors: {e}")
            raise

    async def get_error_summary(
        self,
        project_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict:
        """Get error summary statistics."""
        try:
            conditions = [CrawlError.project_id == project_id]
            
            if from_date:
                conditions.append(CrawlError.created_at >= from_date)
            if to_date:
                conditions.append(CrawlError.created_at <= to_date)

            # Total errors
            total_query = select(func.count(CrawlError.id)).where(and_(*conditions))
            total_errors = (await self.db.execute(total_query)).scalar() or 0

            # Error by category
            category_query = (
                select(CrawlError.error_category, func.count())
                .where(and_(*conditions))
                .group_by(CrawlError.error_category)
            )
            category_result = await self.db.execute(category_query)
            error_by_category = dict(category_result.fetchall())

            # Error by code
            code_query = (
                select(CrawlError.error_code, func.count())
                .where(and_(*conditions))
                .group_by(CrawlError.error_code)
                .order_by(desc(func.count()))
                .limit(10)  # Top 10 error codes
            )
            code_result = await self.db.execute(code_query)
            error_by_code = dict(code_result.fetchall())

            return {
                "total_errors": total_errors,
                "error_by_category": error_by_category,
                "error_by_code": error_by_code,
            }

        except Exception as e:
            logger.error(f"Error getting error summary: {e}")
            raise
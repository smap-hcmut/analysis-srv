"""Crawl errors API route."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logger import logger
from interfaces.analytics_api_repository import ErrorFilters
from models.schemas.base import PaginatedResponse, PaginationParams, create_pagination_info
from models.schemas.errors import CrawlErrorItem, ErrorFiltersRequest
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


@router.get("/errors", response_model=PaginatedResponse[CrawlErrorItem])
async def get_crawl_errors(
    request: Request,
    filters: ErrorFiltersRequest = Depends(),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated crawl errors with filtering."""
    try:
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.info(
            f"Request {request_id}: Getting crawl errors for project {filters.project_id}, "
            f"page {pagination.page}, size {pagination.page_size}"
        )
        
        # Create repository
        repo = AnalyticsApiRepository(db)
        
        # Convert request filters to repository filters
        error_filters = ErrorFilters(
            project_id=filters.project_id,
            job_id=filters.job_id,
            error_code=filters.error_code,
            from_date=filters.from_date,
            to_date=filters.to_date,
        )
        
        # Get crawl errors
        errors, total_count = await repo.get_crawl_errors(
            filters=error_filters,
            pagination=pagination,
        )
        
        # Convert to response format
        error_items = []
        for error in errors:
            error_item = CrawlErrorItem(
                id=error.id,
                content_id=error.content_id,
                platform=error.platform,
                error_code=error.error_code,
                error_category=error.error_category,
                error_message=error.error_message,
                permalink=error.permalink,
                job_id=error.job_id,
                created_at=error.created_at,
            )
            error_items.append(error_item)
        
        return PaginatedResponse(
            success=True,
            data=error_items,
            meta=create_pagination_info(
                page=pagination.page,
                page_size=pagination.page_size,
                total_items=total_count
            ),
        )
        
    except Exception as e:
        logger.error(f"Error in get_crawl_errors: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
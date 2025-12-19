"""Summary statistics API route."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logger import logger
from models.schemas.base import ApiResponse, FilterParams, DateRangeParams
from models.schemas.summary import SummaryData, EngagementTotals
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


class SummaryFiltersRequest(FilterParams, DateRangeParams):
    """Summary request filters."""
    pass


@router.get("/summary", response_model=ApiResponse[SummaryData])
async def get_summary(
    request: Request,
    filters: SummaryFiltersRequest = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated summary statistics for dashboard overview."""
    try:
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.info(
            f"Request {request_id}: Getting summary for project {filters.project_id}"
        )
        
        # Create repository
        repo = AnalyticsApiRepository(db)
        
        # Get summary statistics
        summary_stats = await repo.get_summary_stats(
            project_id=filters.project_id,
            brand_name=filters.brand_name,
            keyword=filters.keyword,
            from_date=filters.from_date,
            to_date=filters.to_date,
        )
        
        # Convert to response format
        engagement_totals = EngagementTotals(**summary_stats["engagement_totals"])
        
        summary_data = SummaryData(
            total_posts=summary_stats["total_posts"],
            total_comments=summary_stats["total_comments"],
            sentiment_distribution=summary_stats["sentiment_distribution"],
            avg_sentiment_score=summary_stats["avg_sentiment_score"],
            risk_distribution=summary_stats["risk_distribution"],
            intent_distribution=summary_stats["intent_distribution"],
            platform_distribution=summary_stats["platform_distribution"],
            engagement_totals=engagement_totals,
            viral_count=summary_stats["viral_count"],
            kol_count=summary_stats["kol_count"],
            avg_impact_score=summary_stats["avg_impact_score"],
        )
        
        return ApiResponse(
            success=True,
            data=summary_data,
        )
        
    except Exception as e:
        logger.error(f"Error in get_summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
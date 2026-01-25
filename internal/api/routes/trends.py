"""Trends API route for time-series analytics data."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logger import logger
from models.schemas.base import ApiResponse, FilterParams
from models.schemas.trends import TrendsData, TrendItem, SentimentBreakdown, TrendsRequest
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


class TrendsFiltersRequest(FilterParams):
    """Trends request filters."""
    granularity: str = Query(default="day", pattern="^(day|week|month)$")
    from_date: datetime = Query(description="Start date (required)")
    to_date: datetime = Query(description="End date (required)")


@router.get("/trends", response_model=ApiResponse[TrendsData])
async def get_trends(
    request: Request,
    filters: TrendsFiltersRequest = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Get time-series trends data for dashboard charts."""
    try:
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.info(
            f"Request {request_id}: Getting trends for project {filters.project_id}, "
            f"granularity {filters.granularity}, "
            f"from {filters.from_date} to {filters.to_date}"
        )
        
        # Create repository
        repo = AnalyticsApiRepository(db)
        
        # Get trends data
        trends_raw = await repo.get_trends_data(
            project_id=filters.project_id,
            granularity=filters.granularity,
            from_date=filters.from_date,
            to_date=filters.to_date,
            brand_name=filters.brand_name,
            keyword=filters.keyword,
        )
        
        # Convert to response format
        trend_items = []
        for item in trends_raw:
            sentiment_breakdown = SentimentBreakdown(
                POSITIVE=item["sentiment_breakdown"]["POSITIVE"],
                NEUTRAL=item["sentiment_breakdown"]["NEUTRAL"],
                NEGATIVE=item["sentiment_breakdown"]["NEGATIVE"],
            )
            
            trend_item = TrendItem(
                date=item["date"],
                post_count=item["post_count"],
                comment_count=item["comment_count"],
                avg_sentiment_score=item["avg_sentiment_score"],
                avg_impact_score=item["avg_impact_score"],
                sentiment_breakdown=sentiment_breakdown,
                total_views=item["total_views"],
                total_likes=item["total_likes"],
                viral_count=item["viral_count"],
                crisis_count=item["crisis_count"],
            )
            trend_items.append(trend_item)
        
        trends_data = TrendsData(
            granularity=filters.granularity,
            items=trend_items
        )
        
        return ApiResponse(
            success=True,
            data=trends_data,
        )
        
    except Exception as e:
        logger.error(f"Error in get_trends: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
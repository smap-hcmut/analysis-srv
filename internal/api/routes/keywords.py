"""Top keywords API route."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logger import logger
from models.schemas.base import ApiResponse, FilterParams, DateRangeParams
from models.schemas.keywords import KeywordsData, TopKeyword, KeywordSentimentBreakdown, KeywordsRequest
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


class KeywordsFiltersRequest(FilterParams, DateRangeParams, KeywordsRequest):
    """Keywords request filters."""
    pass


@router.get("/top-keywords", response_model=ApiResponse[KeywordsData])
async def get_top_keywords(
    request: Request,
    filters: KeywordsFiltersRequest = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Get top keywords with sentiment analysis."""
    try:
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.info(
            f"Request {request_id}: Getting top {filters.limit} keywords for project {filters.project_id}"
        )
        
        # Create repository
        repo = AnalyticsApiRepository(db)
        
        # Get top keywords
        keywords_raw = await repo.get_top_keywords(
            project_id=filters.project_id,
            limit=filters.limit,
            brand_name=filters.brand_name,
            keyword=filters.keyword,
            from_date=filters.from_date,
            to_date=filters.to_date,
        )
        
        # Convert to response format
        keywords = []
        for kw in keywords_raw:
            sentiment_breakdown = KeywordSentimentBreakdown(
                POSITIVE=kw["sentiment_breakdown"]["POSITIVE"],
                NEUTRAL=kw["sentiment_breakdown"]["NEUTRAL"],
                NEGATIVE=kw["sentiment_breakdown"]["NEGATIVE"],
            )
            
            top_keyword = TopKeyword(
                keyword=kw["keyword"],
                count=kw["count"],
                avg_sentiment_score=kw["avg_sentiment_score"],
                aspect=kw["aspect"],
                sentiment_breakdown=sentiment_breakdown,
            )
            keywords.append(top_keyword)
        
        keywords_data = KeywordsData(keywords=keywords)
        
        return ApiResponse(
            success=True,
            data=keywords_data,
        )
        
    except Exception as e:
        logger.error(f"Error in get_top_keywords: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
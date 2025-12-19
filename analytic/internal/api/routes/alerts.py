"""Alerts API route for posts requiring attention."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logger import logger
from models.schemas.base import ApiResponse, FilterParams
from models.schemas.alerts import AlertsData, AlertPost, AlertSummary, AlertsRequest
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


class AlertsFiltersRequest(FilterParams, AlertsRequest):
    """Alerts request filters."""
    pass


@router.get("/alerts", response_model=ApiResponse[AlertsData])
async def get_alerts(
    request: Request,
    filters: AlertsFiltersRequest = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Get posts requiring attention (critical, viral, crisis)."""
    try:
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.info(
            f"Request {request_id}: Getting alerts for project {filters.project_id}, limit {filters.limit}"
        )
        
        # Create repository
        repo = AnalyticsApiRepository(db)
        
        # Get alert posts
        alerts_raw = await repo.get_alert_posts(
            project_id=filters.project_id,
            limit=filters.limit,
            brand_name=filters.brand_name,
            keyword=filters.keyword,
        )
        
        # Convert to response format
        def convert_to_alert_post(post):
            # Truncate content for alerts view
            content_text = post.content_text
            if content_text and len(content_text) > 200:
                content_text = content_text[:200] + "..."
                
            return AlertPost(
                id=post.id,
                content_text=content_text,
                risk_level=post.risk_level,
                impact_score=post.impact_score,
                overall_sentiment=post.overall_sentiment,
                primary_intent=post.primary_intent,
                is_viral=post.is_viral,
                view_count=post.view_count,
                published_at=post.published_at,
                permalink=post.permalink,
            )
        
        critical_posts = [convert_to_alert_post(post) for post in alerts_raw["critical_posts"]]
        viral_posts = [convert_to_alert_post(post) for post in alerts_raw["viral_posts"]]
        crisis_intents = [convert_to_alert_post(post) for post in alerts_raw["crisis_intents"]]
        
        summary = AlertSummary(
            critical_count=alerts_raw["summary"]["critical_count"],
            viral_count=alerts_raw["summary"]["viral_count"],
            crisis_count=alerts_raw["summary"]["crisis_count"],
        )
        
        alerts_data = AlertsData(
            critical_posts=critical_posts,
            viral_posts=viral_posts,
            crisis_intents=crisis_intents,
            summary=summary,
        )
        
        return ApiResponse(
            success=True,
            data=alerts_data,
        )
        
    except Exception as e:
        logger.error(f"Error in get_alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
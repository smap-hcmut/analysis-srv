"""Health check API routes."""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from repository.analytics_api_repository import AnalyticsApiRepository

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Detailed health check with dependency status."""
    # Check database connectivity
    repo = AnalyticsApiRepository(db)
    db_healthy = await repo.health_check()
    
    overall_status = "healthy" if db_healthy else "unhealthy"
    
    return {
        "status": overall_status,
        "version": settings.service_version,
        "service": settings.service_name,
        "dependencies": {
            "database": "healthy" if db_healthy else "unhealthy",
        },
        "uptime": "unknown"  # TODO: Implement uptime tracking
    }
"""Crawl errors schemas."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from models.schemas.base import FilterParams, PaginationParams, DateRangeParams


class ErrorFiltersRequest(FilterParams, DateRangeParams):
    """Request filters for errors endpoint."""
    job_id: Optional[str] = Field(default=None, description="Job ID filter")
    error_code: Optional[str] = Field(default=None, description="Error code filter")


class CrawlErrorItem(BaseModel):
    """Crawl error item."""
    id: int
    content_id: str
    platform: str
    error_code: str
    error_category: str
    error_message: Optional[str]
    permalink: Optional[str]
    job_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ErrorSummary(BaseModel):
    """Error statistics summary."""
    total_errors: int
    error_by_category: Dict[str, int]
    error_by_code: Dict[str, int]
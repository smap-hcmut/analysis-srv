"""Alerts schemas for posts requiring attention."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AlertPost(BaseModel):
    """Post requiring attention (simplified view)."""
    id: str
    content_text: Optional[str] = Field(description="Content preview")
    risk_level: Optional[str]
    impact_score: float
    overall_sentiment: str
    primary_intent: Optional[str]
    is_viral: Optional[bool]
    view_count: int
    published_at: datetime
    permalink: Optional[str]

    class Config:
        from_attributes = True


class AlertSummary(BaseModel):
    """Summary counts for alerts."""
    critical_count: int
    viral_count: int
    crisis_count: int


class AlertsData(BaseModel):
    """Alerts response data."""
    critical_posts: List[AlertPost] = Field(description="Posts with CRITICAL risk level")
    viral_posts: List[AlertPost] = Field(description="Viral posts")
    crisis_intents: List[AlertPost] = Field(description="Posts with CRISIS intent")
    summary: AlertSummary


class AlertsRequest(BaseModel):
    """Alerts query parameters."""
    limit: int = Field(default=10, ge=1, le=50, description="Items per category")
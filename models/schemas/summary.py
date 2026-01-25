"""Summary statistics schemas."""

from typing import Dict
from pydantic import BaseModel, Field


class EngagementTotals(BaseModel):
    """Total engagement metrics."""
    views: int
    likes: int
    comments: int
    shares: int
    saves: int


class SummaryData(BaseModel):
    """Summary statistics response data."""
    total_posts: int = Field(description="Total number of posts")
    total_comments: int = Field(description="Total number of comments")
    
    # Distribution breakdowns
    sentiment_distribution: Dict[str, int] = Field(description="Posts by sentiment")
    avg_sentiment_score: float = Field(description="Average sentiment score")
    
    risk_distribution: Dict[str, int] = Field(description="Posts by risk level")
    intent_distribution: Dict[str, int] = Field(description="Posts by intent")
    platform_distribution: Dict[str, int] = Field(description="Posts by platform")
    
    # Aggregated metrics
    engagement_totals: EngagementTotals
    
    # Special counts
    viral_count: int = Field(description="Number of viral posts")
    kol_count: int = Field(description="Number of KOL posts")
    avg_impact_score: float = Field(description="Average impact score")
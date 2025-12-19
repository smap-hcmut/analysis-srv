"""Trends data schemas."""

from typing import Dict, List
from pydantic import BaseModel, Field


class SentimentBreakdown(BaseModel):
    """Sentiment counts for a time period."""
    POSITIVE: int
    NEUTRAL: int
    NEGATIVE: int


class TrendItem(BaseModel):
    """Single trend data point."""
    date: str = Field(description="Date in YYYY-MM-DD format")
    post_count: int
    comment_count: int
    avg_sentiment_score: float
    avg_impact_score: float
    sentiment_breakdown: SentimentBreakdown
    total_views: int
    total_likes: int
    viral_count: int
    crisis_count: int


class TrendsRequest(BaseModel):
    """Trends query parameters."""
    granularity: str = Field(default="day", pattern="^(day|week|month)$")


class TrendsData(BaseModel):
    """Trends response data."""
    granularity: str
    items: List[TrendItem]
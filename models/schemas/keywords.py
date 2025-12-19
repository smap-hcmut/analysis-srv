"""Keywords analysis schemas."""

from typing import Dict, List
from pydantic import BaseModel, Field


class KeywordSentimentBreakdown(BaseModel):
    """Sentiment breakdown for a keyword."""
    POSITIVE: int
    NEUTRAL: int
    NEGATIVE: int


class TopKeyword(BaseModel):
    """Top keyword with statistics."""
    keyword: str
    count: int
    avg_sentiment_score: float
    aspect: str
    sentiment_breakdown: KeywordSentimentBreakdown


class KeywordsData(BaseModel):
    """Top keywords response data."""
    keywords: List[TopKeyword]


class KeywordsRequest(BaseModel):
    """Keywords query parameters."""
    limit: int = Field(default=20, ge=1, le=50, description="Number of keywords to return")
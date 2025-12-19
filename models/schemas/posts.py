"""Post-related schemas for API requests/responses."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.schemas.base import FilterParams, PaginationParams, DateRangeParams


class PostFiltersRequest(FilterParams, DateRangeParams):
    """Request filters for posts endpoint."""
    platform: Optional[str] = Field(default=None, description="Platform filter")
    sentiment: Optional[str] = Field(default=None, description="Sentiment filter")
    risk_level: Optional[str] = Field(default=None, description="Risk level filter")
    intent: Optional[str] = Field(default=None, description="Intent filter")
    is_viral: Optional[bool] = Field(default=None, description="Viral posts filter")
    is_kol: Optional[bool] = Field(default=None, description="KOL posts filter")


class PostSortingRequest(BaseModel):
    """Sorting options for posts."""
    sort_by: str = Field(default="analyzed_at", description="Sort column")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class PostListItem(BaseModel):
    """Post item in list view (truncated content)."""
    id: str
    platform: str
    permalink: Optional[str]
    content_text: Optional[str] = Field(description="Truncated content (300 chars)")
    
    # Author info
    author_name: Optional[str]
    author_username: Optional[str]
    author_is_verified: Optional[bool]
    
    # Analysis results
    overall_sentiment: str
    overall_sentiment_score: float
    primary_intent: str
    impact_score: float
    risk_level: str
    is_viral: bool
    is_kol: bool
    
    # Metrics
    view_count: int
    like_count: int
    comment_count: int
    
    # Timestamps
    published_at: datetime
    analyzed_at: datetime
    
    # Context (important for filtering/grouping)
    brand_name: Optional[str]
    keyword: Optional[str]
    job_id: Optional[str]

    class Config:
        from_attributes = True


class AspectBreakdown(BaseModel):
    """Aspect sentiment breakdown."""
    sentiment: str
    score: float
    confidence: float
    keywords: List[str]


class KeywordItem(BaseModel):
    """Individual keyword with sentiment."""
    keyword: str
    aspect: str
    sentiment: str
    score: float


class ImpactBreakdown(BaseModel):
    """Impact score breakdown."""
    engagement_score: float
    reach_score: float
    platform_multiplier: float
    sentiment_amplifier: float
    raw_impact: float


class SentimentProbabilities(BaseModel):
    """Sentiment probability distribution."""
    POSITIVE: float
    NEUTRAL: float
    NEGATIVE: float


class CommentItem(BaseModel):
    """Comment in post detail."""
    id: int
    comment_id: Optional[str]
    text: str
    author_name: Optional[str]
    likes: Optional[int]
    sentiment: Optional[str]
    sentiment_score: Optional[float]
    commented_at: Optional[datetime]

    class Config:
        from_attributes = True


class PostDetail(BaseModel):
    """Complete post details."""
    id: str
    platform: str
    permalink: Optional[str]
    
    # Content
    content_text: Optional[str]
    content_transcription: Optional[str]
    hashtags: Optional[List[str]]
    media_duration: Optional[int]
    
    # Author
    author_id: Optional[str]
    author_name: Optional[str]
    author_username: Optional[str]
    author_avatar_url: Optional[str]
    author_is_verified: Optional[bool]
    follower_count: int
    
    # Analysis
    overall_sentiment: str
    overall_sentiment_score: float
    overall_confidence: float
    sentiment_probabilities: Optional[SentimentProbabilities]
    
    primary_intent: str
    intent_confidence: float
    
    impact_score: float
    risk_level: str
    is_viral: bool
    is_kol: bool
    impact_breakdown: Optional[ImpactBreakdown]
    
    aspects_breakdown: Optional[Dict[str, AspectBreakdown]]
    keywords: Optional[List[KeywordItem]]
    
    # Metrics
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    save_count: int
    
    # Timestamps
    published_at: datetime
    analyzed_at: datetime
    crawled_at: Optional[datetime]
    
    # Context
    brand_name: Optional[str]
    keyword: Optional[str]
    job_id: Optional[str]
    
    # Comments
    comments: List[CommentItem]
    comments_total: int

    class Config:
        from_attributes = True
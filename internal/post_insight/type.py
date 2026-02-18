from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, List, Optional


@dataclass
class CreatePostInsightInput:
    # Required Core
    project_id: str
    source_id: Optional[str] = None

    # Content
    content_text: Optional[str] = None
    published_at: Optional[datetime | str] = None
    crawled_at: Optional[datetime | str] = None
    platform: Optional[str] = None
    permalink: Optional[str] = None

    # Author & Engagement (for uap_metadata)
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    follower_count: Optional[int] = None
    author_is_verified: Optional[bool] = None

    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    save_count: Optional[int] = None

    hashtags: List[str] = field(default_factory=list)

    # Analysis Results
    overall_sentiment: str = "NEUTRAL"
    overall_sentiment_score: float = 0.0
    overall_confidence: float = 0.0

    aspects_breakdown: Optional[dict[str, Any]] = None
    keywords: List[str] = field(default_factory=list)

    risk_level: str = "LOW"
    risk_factors: List[Any] = field(default_factory=list)

    primary_intent: str = "DISCUSSION"
    intent_confidence: float = 0.0
    is_spam: bool = False

    # Scores
    engagement_score: float = 0.0
    virality_score: float = 0.0
    influence_score: float = 0.0
    impact_score: float = 0.0

    # Meta
    processing_time_ms: int = 0
    model_version: str = "1.0.0"
    processing_status: str = "success"
    analyzed_at: Optional[datetime | str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for repository processing."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class UpdatePostInsightInput:
    id: str
    # Analysis & Scores
    overall_sentiment: Optional[str] = None
    overall_sentiment_score: Optional[float] = None
    overall_confidence: Optional[float] = None

    risk_level: Optional[str] = None
    risk_factors: Optional[List[Any]] = None

    engagement_score: Optional[float] = None
    virality_score: Optional[float] = None
    influence_score: Optional[float] = None
    impact_score: Optional[float] = None

    # Breakdowns
    aspects_breakdown: Optional[dict[str, Any]] = None
    keywords: Optional[List[str]] = None

    # Meta
    processing_status: Optional[str] = None
    analyzed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and k != "id"}


__all__ = ["CreatePostInsightInput", "UpdatePostInsightInput"]

"""Data types for Analytics Pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .constant import *


@dataclass
class Config:
    """Configuration for analytics pipeline."""

    model_version: str = MODEL_VERSION
    enable_preprocessing: bool = True
    enable_intent_classification: bool = True
    enable_keyword_extraction: bool = True
    enable_sentiment_analysis: bool = True
    enable_impact_calculation: bool = True

    def __post_init__(self):
        if not self.model_version:
            raise ValueError("model_version cannot be empty")


@dataclass
class PostData:
    """Raw post data from crawler (Atomic JSON format)."""

    meta: dict[str, Any] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)
    interaction: dict[str, Any] = field(default_factory=dict)
    author: dict[str, Any] = field(default_factory=dict)
    comments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EventMetadata:
    """Event metadata from RabbitMQ message."""

    event_id: Optional[str] = None
    event_type: Optional[str] = None
    timestamp: Optional[str] = None
    minio_path: Optional[str] = None
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    batch_index: Optional[int] = None
    content_count: Optional[int] = None
    platform: Optional[str] = None
    task_type: Optional[str] = None
    brand_name: Optional[str] = None
    keyword: Optional[str] = None


@dataclass
class EnrichedPostData:
    """Post data enriched with event metadata."""

    meta: dict[str, Any]
    content: dict[str, Any]
    interaction: dict[str, Any]
    author: dict[str, Any]
    comments: list[dict[str, Any]]


@dataclass
class Input:
    """Input structure for analytics pipeline."""

    post_data: PostData
    event_metadata: Optional[EventMetadata] = None
    project_id: Optional[str] = None

    def __post_init__(self):
        if not self.post_data:
            raise ValueError("post_data is required")
        if not self.post_data.meta.get("id"):
            raise ValueError("post_data.meta.id is required")


@dataclass
class AnalyticsResult:
    """Analytics result for a single post."""

    # Identifiers
    id: str
    project_id: Optional[str] = None
    platform: str = PLATFORM_UNKNOWN

    # Timestamps
    published_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None

    # Sentiment
    overall_sentiment: str = DEFAULT_SENTIMENT_LABEL
    overall_sentiment_score: float = DEFAULT_SENTIMENT_SCORE
    overall_confidence: float = DEFAULT_CONFIDENCE

    # Intent
    primary_intent: str = "DISCUSSION"
    intent_confidence: float = DEFAULT_CONFIDENCE

    # Impact
    impact_score: float = DEFAULT_IMPACT_SCORE
    risk_level: str = DEFAULT_RISK_LEVEL
    is_viral: bool = DEFAULT_IS_VIRAL
    is_kol: bool = DEFAULT_IS_KOL

    # Breakdowns (JSONB)
    aspects_breakdown: dict[str, Any] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    sentiment_probabilities: dict[str, float] = field(default_factory=dict)
    impact_breakdown: dict[str, Any] = field(default_factory=dict)

    # Raw metrics
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    save_count: int = 0
    follower_count: int = 0

    # Processing metadata
    processing_time_ms: int = 0
    model_version: str = MODEL_VERSION
    processing_status: str = STATUS_SUCCESS

    # Crawler metadata (Contract v2.0)
    job_id: Optional[str] = None
    batch_index: Optional[int] = None
    task_type: Optional[str] = None
    keyword_source: Optional[str] = None
    crawled_at: Optional[datetime] = None
    pipeline_version: Optional[str] = None
    brand_name: Optional[str] = None
    keyword: Optional[str] = None
    content_text: Optional[str] = None
    content_transcription: Optional[str] = None
    media_duration: Optional[int] = None
    hashtags: Optional[list[str]] = None
    permalink: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    author_avatar_url: Optional[str] = None
    author_is_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for repository."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "platform": self.platform,
            "published_at": self.published_at,
            "analyzed_at": self.analyzed_at,
            "overall_sentiment": self.overall_sentiment,
            "overall_sentiment_score": self.overall_sentiment_score,
            "overall_confidence": self.overall_confidence,
            "primary_intent": self.primary_intent,
            "intent_confidence": self.intent_confidence,
            "impact_score": self.impact_score,
            "risk_level": self.risk_level,
            "is_viral": self.is_viral,
            "is_kol": self.is_kol,
            "aspects_breakdown": self.aspects_breakdown,
            "keywords": self.keywords,
            "sentiment_probabilities": self.sentiment_probabilities,
            "impact_breakdown": self.impact_breakdown,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "share_count": self.share_count,
            "save_count": self.save_count,
            "follower_count": self.follower_count,
            "processing_time_ms": self.processing_time_ms,
            "model_version": self.model_version,
            "job_id": self.job_id,
            "batch_index": self.batch_index,
            "task_type": self.task_type,
            "keyword_source": self.keyword_source,
            "crawled_at": self.crawled_at,
            "pipeline_version": self.pipeline_version,
            "brand_name": self.brand_name,
            "keyword": self.keyword,
            "content_text": self.content_text,
            "content_transcription": self.content_transcription,
            "media_duration": self.media_duration,
            "hashtags": self.hashtags,
            "permalink": self.permalink,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "author_username": self.author_username,
            "author_avatar_url": self.author_avatar_url,
            "author_is_verified": self.author_is_verified,
        }


@dataclass
class Output:
    """Output of analytics pipeline processing."""

    result: AnalyticsResult
    processing_status: str = STATUS_SUCCESS
    error_message: Optional[str] = None
    skipped: bool = False


__all__ = [
    "Config",
    "PostData",
    "EventMetadata",
    "EnrichedPostData",
    "Input",
    "AnalyticsResult",
    "Output",
]

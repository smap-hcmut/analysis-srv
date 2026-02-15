"""Database models for analytics."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from .base import Base


class AnalyzedPost(Base):
    """Post analytics data model."""

    __tablename__ = "analyzed_posts"
    __table_args__ = (
        Index("idx_post_analytics_project_id", "project_id"),
        Index("idx_post_analytics_job_id", "job_id"),
        Index("idx_post_analytics_analyzed_at", "analyzed_at"),
        Index("idx_post_analytics_platform", "platform"),
        Index("idx_post_analytics_risk_level", "risk_level"),
        {"schema": "schema_analyst"},
    )

    # Primary key
    id = Column(String(255), primary_key=True)

    # Identifiers
    project_id = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=False, default="UNKNOWN")

    # Timestamps
    published_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)

    # Sentiment
    overall_sentiment = Column(String(50), nullable=False, default="NEUTRAL")
    overall_sentiment_score = Column(Float, nullable=False, default=0.0)
    overall_confidence = Column(Float, nullable=False, default=0.0)

    # Intent
    primary_intent = Column(String(50), nullable=False, default="DISCUSSION")
    intent_confidence = Column(Float, nullable=False, default=0.0)

    # Impact
    impact_score = Column(Float, nullable=False, default=0.0)
    risk_level = Column(String(50), nullable=False, default="LOW")
    is_viral = Column(Boolean, nullable=False, default=False)
    is_kol = Column(Boolean, nullable=False, default=False)

    # Breakdowns (JSONB)
    aspects_breakdown = Column(JSONB, nullable=False, default={})
    keywords = Column(ARRAY(String), nullable=False, default=[])
    sentiment_probabilities = Column(JSONB, nullable=False, default={})
    impact_breakdown = Column(JSONB, nullable=False, default={})

    # Raw metrics
    view_count = Column(Integer, nullable=False, default=0)
    like_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    share_count = Column(Integer, nullable=False, default=0)
    save_count = Column(Integer, nullable=False, default=0)
    follower_count = Column(Integer, nullable=False, default=0)

    # Processing metadata
    processing_time_ms = Column(Integer, nullable=False, default=0)
    model_version = Column(String(50), nullable=False, default="1.0.0")
    processing_status = Column(String(50), nullable=False, default="success")

    # Crawler metadata (Contract v2.0)
    job_id = Column(String(255), nullable=True)
    batch_index = Column(Integer, nullable=True)
    task_type = Column(String(50), nullable=True)
    keyword_source = Column(String(255), nullable=True)
    crawled_at = Column(DateTime(timezone=True), nullable=True)
    pipeline_version = Column(String(50), nullable=True)
    brand_name = Column(String(255), nullable=True)
    keyword = Column(String(255), nullable=True)

    # Content fields
    content_text = Column(String, nullable=True)
    content_transcription = Column(String, nullable=True)
    media_duration = Column(Integer, nullable=True)
    hashtags = Column(ARRAY(String), nullable=True)
    permalink = Column(String, nullable=True)

    # Author fields
    author_id = Column(String(255), nullable=True)
    author_name = Column(String(255), nullable=True)
    author_username = Column(String(255), nullable=True)
    author_avatar_url = Column(String, nullable=True)
    author_is_verified = Column(Boolean, nullable=False, default=False)


__all__ = ["PostAnalytics"]

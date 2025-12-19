"""Database models for Analytics Engine."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PostAnalytics(Base):
    """Post analytics model."""

    __tablename__ = "post_analytics"

    id = Column(String(50), primary_key=True)
    project_id = Column(PG_UUID, nullable=True)  # Changed to nullable for dry-run tasks
    platform = Column(String(20), nullable=False)

    # Timestamps
    published_at = Column(TIMESTAMP, nullable=False)
    analyzed_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

    # Overall analysis
    overall_sentiment = Column(String(10), nullable=False)
    overall_sentiment_score = Column(Float)
    overall_confidence = Column(Float)

    # Intent
    primary_intent = Column(String(20), nullable=False)
    intent_confidence = Column(Float)

    # Impact
    impact_score = Column(Float, nullable=False)
    risk_level = Column(String(10), nullable=False)
    is_viral = Column(Boolean, default=False)
    is_kol = Column(Boolean, default=False)

    # JSONB columns
    aspects_breakdown = Column(JSONB)
    keywords = Column(JSONB)
    sentiment_probabilities = Column(JSONB)
    impact_breakdown = Column(JSONB)

    # Raw metrics
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)

    # Processing metadata
    processing_time_ms = Column(Integer)
    model_version = Column(String(50))

    # Batch context
    job_id = Column(String(100), nullable=True, index=True)
    batch_index = Column(Integer, nullable=True)
    task_type = Column(String(30), nullable=True, index=True)

    # Crawler metadata
    keyword_source = Column(String(200), nullable=True)
    crawled_at = Column(TIMESTAMP, nullable=True)
    pipeline_version = Column(String(50), nullable=True)

    # Content storage (NEW - Contract v2.0)
    content_text = Column(Text, nullable=True)
    content_transcription = Column(Text, nullable=True)
    media_duration = Column(Integer, nullable=True)
    hashtags = Column(JSONB, nullable=True)
    permalink = Column(Text, nullable=True)

    # Author info (NEW - Contract v2.0)
    author_id = Column(String(100), nullable=True)
    author_name = Column(String(200), nullable=True)
    author_username = Column(String(100), nullable=True)
    author_avatar_url = Column(Text, nullable=True)
    author_is_verified = Column(Boolean, nullable=True, default=False)

    # Brand/Keyword for filtering (NEW - Contract v2.0)
    brand_name = Column(String(100), nullable=True)
    keyword = Column(String(200), nullable=True)

    # Error tracking
    fetch_status = Column(String(10), nullable=True, default="success", index=True)
    fetch_error = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True, index=True)
    error_details = Column(JSONB, nullable=True)

    # Relationship to comments
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan")

    # Table-level indexes
    __table_args__ = (
        Index("idx_post_analytics_job_id", "job_id"),
        Index("idx_post_analytics_fetch_status", "fetch_status"),
        Index("idx_post_analytics_task_type", "task_type"),
        Index("idx_post_analytics_error_code", "error_code"),
        Index("idx_post_analytics_brand_name", "brand_name"),
        Index("idx_post_analytics_keyword", "keyword"),
        Index("idx_post_analytics_author_id", "author_id"),
    )


class PostComment(Base):
    """Post comment model for storing and analyzing comments.

    This table stores comments from crawler items separately,
    enabling comment-level sentiment analysis and querying.
    """

    __tablename__ = "post_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(
        String(50),
        ForeignKey("post_analytics.id", ondelete="CASCADE"),
        nullable=False,
    )
    comment_id = Column(String(100), nullable=True)  # Original ID from platform

    # Content
    text = Column(Text, nullable=False)
    author_name = Column(String(200), nullable=True)
    likes = Column(Integer, nullable=True, default=0)

    # Analysis results (filled by Analytics)
    sentiment = Column(String(10), nullable=True)  # POSITIVE/NEGATIVE/NEUTRAL
    sentiment_score = Column(Float, nullable=True)

    # Timestamps
    commented_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

    # Relationship back to post
    post = relationship("PostAnalytics", back_populates="comments")

    # Table-level indexes
    __table_args__ = (
        Index("idx_post_comments_post_id", "post_id"),
        Index("idx_post_comments_sentiment", "sentiment"),
        Index("idx_post_comments_commented_at", "commented_at"),
    )


class CrawlError(Base):
    """Crawl error model for tracking crawler failures.

    This table stores detailed error information from crawler events,
    enabling error analytics and monitoring.
    """

    __tablename__ = "crawl_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(String(50), nullable=False)
    project_id = Column(PG_UUID, nullable=True)  # NULL for dry-run tasks
    job_id = Column(String(100), nullable=False)
    platform = Column(String(20), nullable=False)

    # Error details
    error_code = Column(String(50), nullable=False)
    error_category = Column(String(30), nullable=False)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONB, nullable=True)

    # Content reference
    permalink = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, default=lambda: datetime.now(timezone.utc))

    # Table-level indexes
    __table_args__ = (
        Index("idx_crawl_errors_project_id", "project_id"),
        Index("idx_crawl_errors_error_code", "error_code"),
        Index("idx_crawl_errors_created_at", "created_at"),
        Index("idx_crawl_errors_job_id", "job_id"),
    )

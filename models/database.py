"""Database models for Analytics Engine."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, Float, Index, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import declarative_base

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

    # Error tracking
    fetch_status = Column(String(10), nullable=True, default="success", index=True)
    fetch_error = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True, index=True)
    error_details = Column(JSONB, nullable=True)

    # Table-level indexes
    __table_args__ = (
        Index("idx_post_analytics_job_id", "job_id"),
        Index("idx_post_analytics_fetch_status", "fetch_status"),
        Index("idx_post_analytics_task_type", "task_type"),
        Index("idx_post_analytics_error_code", "error_code"),
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

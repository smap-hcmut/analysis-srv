"""ORM model for analytics.post_insight table.

Stores AI-derived insights for social media posts including:
- Sentiment analysis (overall + aspect-based)
- Risk assessment (level, factors, alerts)
- Impact metrics (engagement, virality, influence)
- Content quality (spam detection, toxicity)
- Keywords and entities extraction

Table: analytics.post_insight
Schema: analytics
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID
from sqlalchemy.sql import func

from .base import Base


class PostInsight(Base):
    """Social media post with AI insights.
    
    Stores comprehensive AI analysis results for social media posts.
    Used for:
    - Analytics dashboards and reporting
    - Risk monitoring and alerting
    - Trend analysis and insights
    - Historical data queries
    
    Table: analytics.post_insight
    Schema: analytics
    """

    __tablename__ = "post_insight"
    __table_args__ = (
        Index("idx_post_insight_project", "project_id"),
        Index("idx_post_insight_source", "source_id"),
        Index("idx_post_insight_created", "content_created_at"),
        Index("idx_post_insight_sentiment", "overall_sentiment"),
        Index("idx_post_insight_risk", "risk_level"),
        Index("idx_post_insight_platform", "platform"),
        Index("idx_post_insight_analyzed", "analyzed_at"),
        {"schema": "analytics"},
    )

    # Identity
    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id = Column(String(255), nullable=False)
    source_id = Column(String(255), nullable=True)

    # UAP Core
    content = Column(Text, nullable=True)
    content_created_at = Column(DateTime(timezone=True), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    platform = Column(String(50), nullable=True)
    uap_metadata = Column(JSONB, nullable=False, server_default="{}")

    # Sentiment
    overall_sentiment = Column(String(20), nullable=False, server_default="NEUTRAL")
    overall_sentiment_score = Column(Float, nullable=False, server_default="0.0")
    sentiment_confidence = Column(Float, nullable=False, server_default="0.0")
    sentiment_explanation = Column(Text, nullable=True)

    # ABSA
    aspects = Column(JSONB, nullable=False, server_default="[]")

    # Keywords
    keywords = Column(ARRAY(String), nullable=False, server_default="{}")

    # Risk
    risk_level = Column(String(20), nullable=False, server_default="LOW")
    risk_score = Column(Float, nullable=False, server_default="0.0")
    risk_factors = Column(JSONB, nullable=False, server_default="[]")
    requires_attention = Column(Boolean, nullable=False, server_default="false")
    alert_triggered = Column(Boolean, nullable=False, server_default="false")

    # Engagement (calculated)
    engagement_score = Column(Float, nullable=False, server_default="0.0")
    virality_score = Column(Float, nullable=False, server_default="0.0")
    influence_score = Column(Float, nullable=False, server_default="0.0")
    reach_estimate = Column(Integer, nullable=False, server_default="0")

    # Quality
    content_quality_score = Column(Float, nullable=False, server_default="0.0")
    is_spam = Column(Boolean, nullable=False, server_default="false")
    is_bot = Column(Boolean, nullable=False, server_default="false")
    language = Column(String(10), nullable=True)
    language_confidence = Column(Float, nullable=False, server_default="0.0")
    toxicity_score = Column(Float, nullable=False, server_default="0.0")
    is_toxic = Column(Boolean, nullable=False, server_default="false")

    # Processing
    primary_intent = Column(String(50), nullable=False, server_default="DISCUSSION")
    intent_confidence = Column(Float, nullable=False, server_default="0.0")
    impact_score = Column(Float, nullable=False, server_default="0.0")
    processing_time_ms = Column(Integer, nullable=False, server_default="0")
    model_version = Column(String(50), nullable=False, server_default="1.0.0")
    processing_status = Column(String(50), nullable=False, server_default="success")

    # Timestamps
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


__all__ = ["PostInsight"]

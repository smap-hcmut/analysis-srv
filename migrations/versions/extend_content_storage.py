"""Extend content storage for Contract v2.0.

Revision ID: extend_content_storage
Revises: add_crawler_integration
Create Date: 2025-12-18

This migration adds:
1. Content fields to post_analytics (text, transcription, duration, hashtags, permalink)
2. Author fields to post_analytics (id, name, username, avatar_url, is_verified)
3. Brand/Keyword fields to post_analytics (brand_name, keyword)
4. New post_comments table for comment storage
5. Indexes for efficient querying
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "extend_content_storage"
down_revision = "add_crawler_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add content storage fields and post_comments table."""

    # ========================================
    # 1. Add content fields to post_analytics
    # ========================================
    op.add_column(
        "post_analytics",
        sa.Column("content_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("content_transcription", sa.Text(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("media_duration", sa.Integer(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("hashtags", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("permalink", sa.Text(), nullable=True),
    )

    # ========================================
    # 2. Add author fields to post_analytics
    # ========================================
    op.add_column(
        "post_analytics",
        sa.Column("author_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("author_name", sa.String(200), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("author_username", sa.String(100), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("author_is_verified", sa.Boolean(), nullable=True, server_default="false"),
    )

    # ========================================
    # 3. Add brand/keyword fields to post_analytics
    # ========================================
    op.add_column(
        "post_analytics",
        sa.Column("brand_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("keyword", sa.String(200), nullable=True),
    )

    # ========================================
    # 4. Create indexes on post_analytics
    # ========================================
    op.create_index("idx_post_analytics_brand_name", "post_analytics", ["brand_name"])
    op.create_index("idx_post_analytics_keyword", "post_analytics", ["keyword"])
    op.create_index("idx_post_analytics_author_id", "post_analytics", ["author_id"])

    # ========================================
    # 5. Create post_comments table
    # ========================================
    op.create_table(
        "post_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(50), nullable=False),
        sa.Column("comment_id", sa.String(100), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("sentiment", sa.String(10), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("commented_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["post_analytics.id"],
            name="fk_post_comments_post_id",
            ondelete="CASCADE",
        ),
    )

    # ========================================
    # 6. Create indexes on post_comments
    # ========================================
    op.create_index("idx_post_comments_post_id", "post_comments", ["post_id"])
    op.create_index("idx_post_comments_sentiment", "post_comments", ["sentiment"])
    op.create_index("idx_post_comments_commented_at", "post_comments", ["commented_at"])


def downgrade() -> None:
    """Remove content storage fields and post_comments table."""

    # Drop indexes from post_comments
    op.drop_index("idx_post_comments_commented_at", table_name="post_comments")
    op.drop_index("idx_post_comments_sentiment", table_name="post_comments")
    op.drop_index("idx_post_comments_post_id", table_name="post_comments")

    # Drop post_comments table
    op.drop_table("post_comments")

    # Drop indexes from post_analytics
    op.drop_index("idx_post_analytics_author_id", table_name="post_analytics")
    op.drop_index("idx_post_analytics_keyword", table_name="post_analytics")
    op.drop_index("idx_post_analytics_brand_name", table_name="post_analytics")

    # Drop brand/keyword columns
    op.drop_column("post_analytics", "keyword")
    op.drop_column("post_analytics", "brand_name")

    # Drop author columns
    op.drop_column("post_analytics", "author_is_verified")
    op.drop_column("post_analytics", "author_avatar_url")
    op.drop_column("post_analytics", "author_username")
    op.drop_column("post_analytics", "author_name")
    op.drop_column("post_analytics", "author_id")

    # Drop content columns
    op.drop_column("post_analytics", "permalink")
    op.drop_column("post_analytics", "hashtags")
    op.drop_column("post_analytics", "media_duration")
    op.drop_column("post_analytics", "content_transcription")
    op.drop_column("post_analytics", "content_text")

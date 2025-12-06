"""Add crawler integration fields.

Revision ID: add_crawler_integration
Revises: dc8d02d16d50
Create Date: 2025-12-06

This migration adds:
1. 10 new fields to post_analytics table for crawler integration
2. New crawl_errors table for error tracking
3. Indexes for efficient querying
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_crawler_integration"
down_revision = "dc8d02d16d50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add crawler integration fields and crawl_errors table."""

    # Add new columns to post_analytics table
    op.add_column(
        "post_analytics",
        sa.Column("job_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("batch_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("task_type", sa.String(30), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("keyword_source", sa.String(200), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("crawled_at", sa.TIMESTAMP(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("pipeline_version", sa.String(50), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("fetch_status", sa.String(10), nullable=True, server_default="success"),
    )
    op.add_column(
        "post_analytics",
        sa.Column("fetch_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("error_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "post_analytics",
        sa.Column("error_details", postgresql.JSONB(), nullable=True),
    )

    # Make project_id nullable (for dry-run tasks)
    op.alter_column(
        "post_analytics",
        "project_id",
        existing_type=postgresql.UUID(),
        nullable=True,
    )

    # Create indexes for post_analytics
    op.create_index("idx_post_analytics_job_id", "post_analytics", ["job_id"])
    op.create_index("idx_post_analytics_fetch_status", "post_analytics", ["fetch_status"])
    op.create_index("idx_post_analytics_task_type", "post_analytics", ["task_type"])
    op.create_index("idx_post_analytics_error_code", "post_analytics", ["error_code"])

    # Create crawl_errors table
    op.create_table(
        "crawl_errors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content_id", sa.String(50), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=True),
        sa.Column("job_id", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=False),
        sa.Column("error_category", sa.String(30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", postgresql.JSONB(), nullable=True),
        sa.Column("permalink", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for crawl_errors
    op.create_index("idx_crawl_errors_project_id", "crawl_errors", ["project_id"])
    op.create_index("idx_crawl_errors_error_code", "crawl_errors", ["error_code"])
    op.create_index("idx_crawl_errors_created_at", "crawl_errors", ["created_at"])
    op.create_index("idx_crawl_errors_job_id", "crawl_errors", ["job_id"])


def downgrade() -> None:
    """Remove crawler integration fields and crawl_errors table."""

    # Drop indexes from crawl_errors
    op.drop_index("idx_crawl_errors_job_id", table_name="crawl_errors")
    op.drop_index("idx_crawl_errors_created_at", table_name="crawl_errors")
    op.drop_index("idx_crawl_errors_error_code", table_name="crawl_errors")
    op.drop_index("idx_crawl_errors_project_id", table_name="crawl_errors")

    # Drop crawl_errors table
    op.drop_table("crawl_errors")

    # Drop indexes from post_analytics
    op.drop_index("idx_post_analytics_error_code", table_name="post_analytics")
    op.drop_index("idx_post_analytics_task_type", table_name="post_analytics")
    op.drop_index("idx_post_analytics_fetch_status", table_name="post_analytics")
    op.drop_index("idx_post_analytics_job_id", table_name="post_analytics")

    # Make project_id non-nullable again
    op.alter_column(
        "post_analytics",
        "project_id",
        existing_type=postgresql.UUID(),
        nullable=False,
    )

    # Drop columns from post_analytics
    op.drop_column("post_analytics", "error_details")
    op.drop_column("post_analytics", "error_code")
    op.drop_column("post_analytics", "fetch_error")
    op.drop_column("post_analytics", "fetch_status")
    op.drop_column("post_analytics", "pipeline_version")
    op.drop_column("post_analytics", "crawled_at")
    op.drop_column("post_analytics", "keyword_source")
    op.drop_column("post_analytics", "task_type")
    op.drop_column("post_analytics", "batch_index")
    op.drop_column("post_analytics", "job_id")

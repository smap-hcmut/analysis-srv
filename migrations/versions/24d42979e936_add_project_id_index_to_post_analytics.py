"""add_project_id_index_to_post_analytics

Revision ID: 24d42979e936
Revises: add_crawler_integration
Create Date: 2025-12-07 02:46:51.921477

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "24d42979e936"
down_revision: Union[str, Sequence[str], None] = "add_crawler_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index on post_analytics.project_id for faster project-level queries.

    Note: For production with large tables, consider running this outside of
    Alembic with CONCURRENTLY option for non-blocking index creation:
    CREATE INDEX CONCURRENTLY idx_post_analytics_project_id ON post_analytics (project_id);
    """
    op.create_index(
        "idx_post_analytics_project_id",
        "post_analytics",
        ["project_id"],
    )


def downgrade() -> None:
    """Remove the project_id index."""
    op.drop_index(
        "idx_post_analytics_project_id",
        table_name="post_analytics",
    )

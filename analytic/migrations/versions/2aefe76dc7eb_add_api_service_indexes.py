"""add_api_service_indexes

Revision ID: 2aefe76dc7eb
Revises: b5146412efe5
Create Date: 2025-12-19 16:12:00.191105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2aefe76dc7eb'
down_revision: Union[str, Sequence[str], None] = 'b5146412efe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for API service query optimization."""
    # Composite indexes for common filter combinations
    op.create_index(
        'idx_post_analytics_project_brand',
        'post_analytics',
        ['project_id', 'brand_name']
    )
    
    op.create_index(
        'idx_post_analytics_project_brand_keyword',
        'post_analytics',
        ['project_id', 'brand_name', 'keyword']
    )
    
    # Date range queries optimization
    op.create_index(
        'idx_post_analytics_published_at',
        'post_analytics',
        ['published_at']
    )
    
    # Common sorting columns
    op.create_index(
        'idx_post_analytics_impact_score',
        'post_analytics',
        ['impact_score']
    )
    
    op.create_index(
        'idx_post_analytics_analyzed_at',
        'post_analytics',
        ['analyzed_at']
    )
    
    # Alert queries optimization
    op.create_index(
        'idx_post_analytics_risk_level',
        'post_analytics',
        ['risk_level']
    )
    
    op.create_index(
        'idx_post_analytics_is_viral',
        'post_analytics',
        ['is_viral']
    )
    
    op.create_index(
        'idx_post_analytics_primary_intent',
        'post_analytics',
        ['primary_intent']
    )


def downgrade() -> None:
    """Remove API service indexes."""
    op.drop_index('idx_post_analytics_primary_intent', 'post_analytics')
    op.drop_index('idx_post_analytics_is_viral', 'post_analytics')
    op.drop_index('idx_post_analytics_risk_level', 'post_analytics')
    op.drop_index('idx_post_analytics_analyzed_at', 'post_analytics')
    op.drop_index('idx_post_analytics_impact_score', 'post_analytics')
    op.drop_index('idx_post_analytics_published_at', 'post_analytics')
    op.drop_index('idx_post_analytics_project_brand_keyword', 'post_analytics')
    op.drop_index('idx_post_analytics_project_brand', 'post_analytics')

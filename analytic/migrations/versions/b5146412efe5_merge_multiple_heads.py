"""merge_multiple_heads

Revision ID: b5146412efe5
Revises: 24d42979e936, extend_content_storage
Create Date: 2025-12-18 19:57:59.277822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5146412efe5'
down_revision: Union[str, Sequence[str], None] = ('24d42979e936', 'extend_content_storage')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

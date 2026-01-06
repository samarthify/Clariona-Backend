"""add keyword_groups column to topics

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add keyword_groups column to topics table for AND/OR keyword logic."""
    
    # Add keyword_groups column (JSONB for PostgreSQL)
    op.add_column('topics',
        sa.Column('keyword_groups', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    
    # Create index on keyword_groups for efficient queries
    op.create_index(
        'idx_topics_keyword_groups',
        'topics',
        ['keyword_groups'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Remove keyword_groups column from topics table."""
    
    op.drop_index('idx_topics_keyword_groups', table_name='topics')
    op.drop_column('topics', 'keyword_groups')














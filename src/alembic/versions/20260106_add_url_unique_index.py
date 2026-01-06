"""add unique index on sentiment_data url

Revision ID: add_url_unique_index
Revises: 
Create Date: 2026-01-06 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_url_unique_index'
down_revision = '7ea046c4dadc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique index on sentiment_data.url for upsert support."""
    # Create unique index on url column
    # Using partial index to only include non-null urls
    op.create_index(
        'ix_sentiment_data_url_unique',
        'sentiment_data',
        ['url'],
        unique=True,
        postgresql_where=sa.text('url IS NOT NULL')
    )


def downgrade() -> None:
    """Remove unique index on sentiment_data.url."""
    op.drop_index('ix_sentiment_data_url_unique', table_name='sentiment_data')

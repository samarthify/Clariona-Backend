"""Add index to sentiment_label

Revision ID: 20260106_add_sentiment_label_index
Revises: 20260106_add_url_unique_index
Create Date: 2026-01-06 02:16:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_sent_idx'
down_revision = 'add_url_unique_index'
branch_labels = None
depends_on = None


def upgrade():
    # Create index on sentiment_label column to speed up polling queries
    # "WHERE sentiment_label IS NULL"
    op.create_index(
        'ix_sentiment_data_sentiment_label',
        'sentiment_data',
        ['sentiment_label'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_sentiment_data_sentiment_label', table_name='sentiment_data')

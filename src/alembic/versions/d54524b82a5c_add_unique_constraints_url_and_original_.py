"""add unique constraints url and original_id

Revision ID: d54524b82a5c
Revises: 734447197757
Create Date: 2026-01-06 12:13:54.888055

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd54524b82a5c'
down_revision: Union[str, None] = '734447197757'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add unique constraint for upsert safety on sentiment_data.url
    op.create_unique_constraint(
        "uq_sentiment_data_url",
        "sentiment_data",
        ["url"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_sentiment_data_url", "sentiment_data", type_="unique")

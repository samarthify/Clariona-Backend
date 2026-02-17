"""Add issue_summary column to topic_issues

Revision ID: 20260107_add_issue_summary
Revises: 20260106_add_processing_clusters
Create Date: 2026-01-07 13:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260107_add_issue_summary'
down_revision: Union[str, None] = '20260106_add_processing_clusters'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add issue_summary column to topic_issues table
    op.add_column('topic_issues', sa.Column('issue_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove issue_summary column
    op.drop_column('topic_issues', 'issue_summary')

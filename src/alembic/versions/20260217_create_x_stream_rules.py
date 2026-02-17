"""Create x_stream_rules table for X API Filtered Stream

Revision ID: 20260217_x_stream_rules
Revises: 20260212_issue_detection_idx
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '20260217_x_stream_rules'
down_revision: Union[str, None] = '20260212_issue_detection_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'x_stream_rules' in inspector.get_table_names():
        return
    op.create_table(
        'x_stream_rules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('tag', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('x_rule_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('idx_x_stream_rules_active', 'x_stream_rules', ['is_active'])
    op.create_index('idx_x_stream_rules_x_rule_id', 'x_stream_rules', ['x_rule_id'])


def downgrade() -> None:
    op.drop_index('idx_x_stream_rules_x_rule_id', table_name='x_stream_rules')
    op.drop_index('idx_x_stream_rules_active', table_name='x_stream_rules')
    op.drop_table('x_stream_rules')

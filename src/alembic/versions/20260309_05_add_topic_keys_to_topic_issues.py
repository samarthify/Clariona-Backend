"""Add topic_keys to topic_issues for global clustering fan-out

Revision ID: 20260309_05
Revises: 20260309_04
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260309_05"
down_revision: Union[str, None] = "20260309_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "topic_issues", "topic_keys"):
        op.add_column(
            "topic_issues",
            sa.Column("topic_keys", postgresql.ARRAY(sa.Text()), nullable=True),
        )

    op.execute("""
        UPDATE topic_issues
        SET topic_keys = ARRAY[topic_key]
        WHERE topic_keys IS NULL OR topic_keys = '{}' OR array_length(topic_keys, 1) IS NULL
    """)


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, "topic_issues", "topic_keys"):
        op.drop_column("topic_issues", "topic_keys")

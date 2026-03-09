"""Add topic_keys array column to cluster_queue for global clustering

Revision ID: 20260309_02
Revises: 20260309_01
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260309_02"
down_revision: Union[str, None] = "20260309_01"
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

    if not _column_exists(bind, "cluster_queue", "topic_keys"):
        op.add_column(
            "cluster_queue",
            sa.Column(
                "topic_keys",
                postgresql.ARRAY(sa.Text()),
                nullable=True,
                server_default="{}",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _column_exists(bind, "cluster_queue", "topic_keys"):
        op.drop_column("cluster_queue", "topic_keys")

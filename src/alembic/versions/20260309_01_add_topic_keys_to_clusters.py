"""Add topic_keys array column to processing_clusters for global clustering

Revision ID: 20260309_01
Revises: 20260226_schema
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260309_01"
down_revision: Union[str, None] = "20260226_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def _index_exists(bind, table: str, index_name: str) -> bool:
    for idx in sa.inspect(bind).get_indexes(table):
        if idx.get("name") == index_name:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()

    # Add topic_keys column to processing_clusters
    if not _column_exists(bind, "processing_clusters", "topic_keys"):
        op.add_column(
            "processing_clusters",
            sa.Column(
                "topic_keys",
                postgresql.ARRAY(sa.Text()),
                nullable=True,
                server_default="{}",
            ),
        )

    # Backfill: set topic_keys from topic_key where empty
    op.execute("""
        UPDATE processing_clusters
        SET topic_keys = ARRAY[topic_key]
        WHERE topic_keys IS NULL OR topic_keys = '{}' OR array_length(topic_keys, 1) IS NULL
    """)

    # Remove user-scoped index for global clustering (status-only filter)
    # idx_processing_clusters_status already exists from 20260106
    if _index_exists(bind, "processing_clusters", "idx_processing_clusters_user_status"):
        op.drop_index(
            "idx_processing_clusters_user_status",
            table_name="processing_clusters",
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Recreate user_status index if rolling back
    if not _index_exists(bind, "processing_clusters", "idx_processing_clusters_user_status"):
        op.create_index(
            "idx_processing_clusters_user_status",
            "processing_clusters",
            ["user_id", "status"],
            unique=False,
        )

    if _column_exists(bind, "processing_clusters", "topic_keys"):
        op.drop_column("processing_clusters", "topic_keys")

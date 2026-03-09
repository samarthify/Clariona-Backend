"""Incremental clustering schema: cluster_id, user_id, sum_vec, version, queue tables

Revision ID: 20260226_schema
Revises: 20260226_incremental
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260226_schema"
down_revision: Union[str, None] = "20260226_incremental"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def _table_exists(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def _index_exists(bind, table: str, index_name: str) -> bool:
    for idx in sa.inspect(bind).get_indexes(table):
        if idx.get("name") == index_name:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()

    # --- sentiment_data.cluster_id ---
    if not _column_exists(bind, "sentiment_data", "cluster_id"):
        op.add_column(
            "sentiment_data",
            sa.Column(
                "cluster_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("processing_clusters.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("idx_sentiment_data_cluster_id", "sentiment_data", ["cluster_id"])

    # --- sentiment_data index for backfill queue ---
    if not _index_exists(bind, "sentiment_data", "idx_sentiment_data_processing_status_created_at"):
        op.create_index(
            "idx_sentiment_data_processing_status_created_at",
            "sentiment_data",
            ["processing_status", "created_at"],
            unique=False,
        )

    # --- processing_clusters.user_id ---
    if not _column_exists(bind, "processing_clusters", "user_id"):
        op.add_column(
            "processing_clusters",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    # --- processing_clusters.sum_vec ---
    if not _column_exists(bind, "processing_clusters", "sum_vec"):
        op.add_column(
            "processing_clusters",
            sa.Column("sum_vec", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    # --- processing_clusters.version ---
    if not _column_exists(bind, "processing_clusters", "version"):
        op.add_column(
            "processing_clusters",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )

    # --- processing_clusters indexes ---
    if not _index_exists(bind, "processing_clusters", "idx_processing_clusters_topic_user_status"):
        op.create_index(
            "idx_processing_clusters_topic_user_status",
            "processing_clusters",
            ["topic_key", "user_id", "status"],
            unique=False,
        )
    if not _index_exists(bind, "processing_clusters", "idx_processing_clusters_status_updated"):
        op.create_index(
            "idx_processing_clusters_status_updated",
            "processing_clusters",
            ["status", "updated_at"],
            unique=False,
        )

    # --- analysis_queue ---
    if not _table_exists(bind, "analysis_queue"):
        op.create_table(
            "analysis_queue",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["entry_id"], ["sentiment_data.entry_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entry_id", name="uq_analysis_queue_entry_id"),
        )
        op.create_index(
            "idx_analysis_queue_pending",
            "analysis_queue",
            ["status", "created_at"],
            unique=False,
            postgresql_where=sa.text("status = 'pending'"),
        )

    # --- cluster_queue ---
    if not _table_exists(bind, "cluster_queue"):
        op.create_table(
            "cluster_queue",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("topic_key", sa.Text(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_cluster_queue_pending",
            "cluster_queue",
            ["status", "created_at"],
            unique=False,
            postgresql_where=sa.text("status = 'pending'"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "cluster_queue"):
        op.drop_index("idx_cluster_queue_pending", table_name="cluster_queue")
        op.drop_table("cluster_queue")

    if _table_exists(bind, "analysis_queue"):
        op.drop_index("idx_analysis_queue_pending", table_name="analysis_queue")
        op.drop_table("analysis_queue")

    if _index_exists(bind, "processing_clusters", "idx_processing_clusters_status_updated"):
        op.drop_index("idx_processing_clusters_status_updated", table_name="processing_clusters")
    if _index_exists(bind, "processing_clusters", "idx_processing_clusters_topic_user_status"):
        op.drop_index("idx_processing_clusters_topic_user_status", table_name="processing_clusters")

    if _column_exists(bind, "processing_clusters", "version"):
        op.drop_column("processing_clusters", "version")
    if _column_exists(bind, "processing_clusters", "sum_vec"):
        op.drop_column("processing_clusters", "sum_vec")
    if _column_exists(bind, "processing_clusters", "user_id"):
        op.drop_column("processing_clusters", "user_id")

    if _column_exists(bind, "sentiment_data", "cluster_id"):
        op.drop_index("idx_sentiment_data_cluster_id", table_name="sentiment_data")
        if _index_exists(bind, "sentiment_data", "idx_sentiment_data_processing_status_created_at"):
            op.drop_index("idx_sentiment_data_processing_status_created_at", table_name="sentiment_data")
        op.drop_column("sentiment_data", "cluster_id")

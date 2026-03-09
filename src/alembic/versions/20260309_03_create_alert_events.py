"""Create alert_events table for crisis/alert audit trail

Revision ID: 20260309_03
Revises: 20260309_02
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260309_03"
down_revision: Union[str, None] = "20260309_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table: str) -> bool:
    return table in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "alert_events"):
        op.create_table(
            "alert_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("cluster_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_clusters.id", ondelete="SET NULL"), nullable=True),
            sa.Column("topic_keys", postgresql.ARRAY(sa.Text()), nullable=True),
            sa.Column("severity", sa.String(20), nullable=True),
            sa.Column("burst_ratio", sa.Float(), nullable=True),
            sa.Column("count_1m", sa.Integer(), nullable=True),
            sa.Column("count_5m", sa.Integer(), nullable=True),
            sa.Column("count_15m", sa.Integer(), nullable=True),
            sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("routed_to", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("cooldown_key", sa.String(255), nullable=True),
        )
        op.create_index(
            "idx_alert_events_user_fired",
            "alert_events",
            ["user_id", "fired_at"],
            unique=False,
        )
        op.create_index(
            "idx_alert_events_cluster_fired",
            "alert_events",
            ["cluster_id", "fired_at"],
            unique=False,
        )
        op.create_index(
            "idx_alert_events_severity",
            "alert_events",
            ["severity"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "alert_events"):
        op.drop_index("idx_alert_events_severity", table_name="alert_events")
        op.drop_index("idx_alert_events_cluster_fired", table_name="alert_events")
        op.drop_index("idx_alert_events_user_fired", table_name="alert_events")
        op.drop_table("alert_events")

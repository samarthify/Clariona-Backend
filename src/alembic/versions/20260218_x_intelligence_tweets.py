"""X intelligence: tweets table, x_stream_rules priority_level, x_rule_run_state

Revision ID: 20260218_x_intel
Revises: 20260217_x_stream_rules
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260218_x_intel"
down_revision: Union[str, None] = "20260217_x_stream_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1) Add priority_level to x_stream_rules (if not already present)
    if "x_stream_rules" in tables:
        cols = [c["name"] for c in inspector.get_columns("x_stream_rules")]
        if "priority_level" not in cols:
            op.add_column(
                "x_stream_rules",
                sa.Column("priority_level", sa.SmallInteger(), nullable=True),
            )

    # 2) Create tweets table (single source of truth for X posts, all 4 layers)
    if "tweets" not in tables:
        op.create_table(
            "tweets",
        sa.Column("tweet_id", sa.String(32), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("x_stream_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("author_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("first_seen_source", sa.String(20), nullable=True),  # stream | rising | stable | safety
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("reply_count", sa.Integer(), nullable=True),
        sa.Column("retweet_count", sa.Integer(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("engagement_score", sa.Numeric(20, 4), nullable=True),
        sa.Column("engagement_velocity", sa.Numeric(20, 6), nullable=True),
        sa.Column("engagement_rate", sa.Numeric(20, 8), nullable=True),
        sa.Column("last_metrics_update_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_count", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("idx_tweets_rule_created", "tweets", ["rule_id", "created_at"])
        op.create_index("idx_tweets_rule_engagement", "tweets", ["rule_id", "engagement_score"])
        op.create_index("idx_tweets_created_at", "tweets", ["created_at"])
        op.create_index("idx_tweets_engagement_velocity", "tweets", ["engagement_velocity"])

    # 3) Throttling state per (rule, layer) for cost control
    if "x_rule_run_state" not in tables:
        op.create_table(
            "x_rule_run_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("x_stream_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layer", sa.String(20), nullable=False),  # rising | stable | safety
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_new_unique_count", sa.Integer(), nullable=True),
        sa.Column("skip_until", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("rule_id", "layer", name="uq_x_rule_run_state_rule_layer"),
        )
        op.create_index("idx_x_rule_run_state_rule_layer", "x_rule_run_state", ["rule_id", "layer"])


def downgrade() -> None:
    op.drop_index("idx_x_rule_run_state_rule_layer", table_name="x_rule_run_state")
    op.drop_table("x_rule_run_state")
    op.drop_index("idx_tweets_engagement_velocity", table_name="tweets")
    op.drop_index("idx_tweets_created_at", table_name="tweets")
    op.drop_index("idx_tweets_rule_engagement", table_name="tweets")
    op.drop_index("idx_tweets_rule_created", table_name="tweets")
    op.drop_table("tweets")
    op.drop_column("x_stream_rules", "priority_level")

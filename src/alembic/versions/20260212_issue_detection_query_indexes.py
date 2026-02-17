"""Add indexes for issue detection NOT EXISTS query performance

Revision ID: 20260212_issue_detection_query_indexes
Revises: 20260107_add_issue_summary
Create Date: 2026-02-12

These indexes are required for the optimized _get_unprocessed_mentions query
(correlated NOT EXISTS). Without them, performance gains are muted.
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20260212_issue_detection_idx'
down_revision: Union[str, None] = '20260107_add_issue_summary'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: CREATE INDEX IF NOT EXISTS
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mt_topic_key ON mention_topics(topic_key, mention_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_issue_mentions_mention_id ON issue_mentions(mention_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cluster_mentions_mention_id ON cluster_mentions(mention_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_processing_clusters_status_id ON processing_clusters(status, id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sentiment_data_entry_id ON sentiment_data(entry_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sentiment_data_entry_id")
    op.execute("DROP INDEX IF EXISTS idx_processing_clusters_status_id")
    op.execute("DROP INDEX IF EXISTS idx_cluster_mentions_mention_id")
    op.execute("DROP INDEX IF EXISTS idx_issue_mentions_mention_id")
    op.execute("DROP INDEX IF EXISTS idx_mt_topic_key")

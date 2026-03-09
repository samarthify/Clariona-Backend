"""Add use_incremental_clustering feature flag to system_configurations

Revision ID: 20260226_incremental
Revises: 20260218_x_intel
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260226_incremental"
down_revision: Union[str, None] = "20260218_x_intel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert feature flag for incremental clustering. Idempotent (ON CONFLICT DO NOTHING)."""
    op.execute("""
        INSERT INTO system_configurations 
        (category, config_key, config_value, config_type, description, is_active, default_value, created_at, updated_at)
        VALUES 
        ('clustering', 'use_incremental_clustering', 'false'::jsonb, 'bool',
         'Enable incremental clustering with Pinecone and queue-based processing (vs batch DBSCAN). Set to true only after full migration is deployed and validated.',
         true, 'false'::jsonb, now(), now())
        ON CONFLICT (category, config_key) DO NOTHING
    """)


def downgrade() -> None:
    """Remove feature flag."""
    op.execute("""
        DELETE FROM system_configurations 
        WHERE category = 'clustering' AND config_key = 'use_incremental_clustering'
    """)


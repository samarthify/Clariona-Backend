"""add_processing_clusters

Revision ID: 20260106_add_processing_clusters
Revises: 7ea046c4dadc
Create Date: 2026-01-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260106_add_processing_clusters'
down_revision: Union[str, None] = 'd54524b82a5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Helpers
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def table_exists(name: str) -> bool:
        return name in inspector.get_table_names()

    def column_exists(table: str, column: str) -> bool:
        if table not in inspector.get_table_names():
            return False
        cols = [c['name'] for c in inspector.get_columns(table)]
        return column in cols

    # processing_clusters
    if not table_exists('processing_clusters'):
        op.create_table(
            'processing_clusters',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('topic_key', sa.String(length=100), nullable=False),
            sa.Column('cluster_type', sa.String(length=50), nullable=False, server_default='dynamic'),
            sa.Column('centroid', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('size', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('density_score', sa.Float(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        )
        op.create_index('idx_processing_clusters_topic', 'processing_clusters', ['topic_key'])
        op.create_index('idx_processing_clusters_status', 'processing_clusters', ['status'])

    # cluster_mentions
    if not table_exists('cluster_mentions'):
        op.create_table(
            'cluster_mentions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('cluster_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('processing_clusters.id', ondelete='CASCADE'), nullable=False),
            sa.Column('mention_id', sa.Integer(), sa.ForeignKey('sentiment_data.entry_id', ondelete='CASCADE'), nullable=False),
            sa.Column('similarity_score', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.UniqueConstraint('cluster_id', 'mention_id', name='uq_cluster_mention'),
        )
        op.create_index('idx_cluster_mentions_cluster', 'cluster_mentions', ['cluster_id'])
        op.create_index('idx_cluster_mentions_mention', 'cluster_mentions', ['mention_id'])

    # issue_mentions.cluster_id
    if not column_exists('issue_mentions', 'cluster_id'):
        op.add_column(
            'issue_mentions',
            sa.Column('cluster_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('processing_clusters.id', ondelete='SET NULL'), nullable=True)
        )
        op.create_index('idx_issue_mentions_cluster', 'issue_mentions', ['cluster_id'])


def downgrade() -> None:
    # Drop added column
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    def column_exists(table: str, column: str) -> bool:
        if table not in inspector.get_table_names():
            return False
        cols = [c['name'] for c in inspector.get_columns(table)]
        return column in cols

    if column_exists('issue_mentions', 'cluster_id'):
        op.drop_index('idx_issue_mentions_cluster', table_name='issue_mentions')
        op.drop_column('issue_mentions', 'cluster_id')

    if 'cluster_mentions' in inspector.get_table_names():
        op.drop_index('idx_cluster_mentions_cluster', table_name='cluster_mentions')
        op.drop_index('idx_cluster_mentions_mention', table_name='cluster_mentions')
        op.drop_table('cluster_mentions')

    if 'processing_clusters' in inspector.get_table_names():
        op.drop_index('idx_processing_clusters_topic', table_name='processing_clusters')
        op.drop_index('idx_processing_clusters_status', table_name='processing_clusters')
        op.drop_table('processing_clusters')

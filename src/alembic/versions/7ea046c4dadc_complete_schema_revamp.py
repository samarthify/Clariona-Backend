"""complete_schema_revamp

Revision ID: 7ea046c4dadc
Revises: d4e5f6a7b8c9
Create Date: 2025-12-29 01:49:03.133840

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7ea046c4dadc'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Complete schema revamp: Issue system, Sentiment system, and enhancements."""
    
    # Helper function to check if table exists
    def table_exists(table_name: str) -> bool:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        return table_name in inspector.get_table_names()
    
    # Helper function to check if column exists
    def column_exists(table_name: str, column_name: str) -> bool:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        if table_name not in inspector.get_table_names():
            return False
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    
    # ============================================
    # 1. ALTER TABLE sentiment_data - Add emotion and influence columns
    # ============================================
    if not column_exists('sentiment_data', 'emotion_label'):
        op.add_column('sentiment_data', 
            sa.Column('emotion_label', sa.String(length=50), nullable=True))
    if not column_exists('sentiment_data', 'emotion_score'):
        op.add_column('sentiment_data', 
            sa.Column('emotion_score', sa.Float(), nullable=True))
    if not column_exists('sentiment_data', 'emotion_distribution'):
        op.add_column('sentiment_data', 
            sa.Column('emotion_distribution', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if not column_exists('sentiment_data', 'influence_weight'):
        op.add_column('sentiment_data', 
            sa.Column('influence_weight', sa.Float(), nullable=True, server_default='1.0'))
    if not column_exists('sentiment_data', 'confidence_weight'):
        op.add_column('sentiment_data', 
            sa.Column('confidence_weight', sa.Float(), nullable=True))
    
    # Add processing status columns for safe concurrent processing
    if not column_exists('sentiment_data', 'processing_status'):
        op.add_column('sentiment_data', 
            sa.Column('processing_status', sa.String(length=20), nullable=True, server_default='pending'))
    if not column_exists('sentiment_data', 'processing_started_at'):
        op.add_column('sentiment_data', 
            sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('sentiment_data', 'processing_completed_at'):
        op.add_column('sentiment_data', 
            sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('sentiment_data', 'processing_error'):
        op.add_column('sentiment_data', 
            sa.Column('processing_error', sa.Text(), nullable=True))
    
    # Set existing records to 'completed' status
    op.execute("""
        UPDATE sentiment_data 
        SET processing_status = 'completed' 
        WHERE processing_status IS NULL 
          AND sentiment_label IS NOT NULL
    """)
    
    # Set records without sentiment to 'pending'
    op.execute("""
        UPDATE sentiment_data 
        SET processing_status = 'pending' 
        WHERE processing_status IS NULL 
          AND sentiment_label IS NULL
    """)
    
    # ============================================
    # 2. ALTER TABLE topic_issues - Enhance with clustering and lifecycle
    # ============================================
    if not column_exists('topic_issues', 'issue_title'):
        op.add_column('topic_issues',
            sa.Column('issue_title', sa.String(length=500), nullable=True))
    if not column_exists('topic_issues', 'primary_topic_key'):
        op.add_column('topic_issues',
            sa.Column('primary_topic_key', sa.String(length=100), nullable=True))
    if not column_exists('topic_issues', 'state'):
        op.add_column('topic_issues',
            sa.Column('state', sa.String(length=50), nullable=True, server_default='emerging'))
    if not column_exists('topic_issues', 'status'):
        op.add_column('topic_issues',
            sa.Column('status', sa.String(length=50), nullable=True))
    if not column_exists('topic_issues', 'start_time'):
        op.add_column('topic_issues',
            sa.Column('start_time', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('topic_issues', 'last_activity'):
        op.add_column('topic_issues',
            sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')))
    if not column_exists('topic_issues', 'resolved_at'):
        op.add_column('topic_issues',
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    if not column_exists('topic_issues', 'volume_current_window'):
        op.add_column('topic_issues',
            sa.Column('volume_current_window', sa.Integer(), nullable=True, server_default='0'))
    if not column_exists('topic_issues', 'volume_previous_window'):
        op.add_column('topic_issues',
            sa.Column('volume_previous_window', sa.Integer(), nullable=True, server_default='0'))
    if not column_exists('topic_issues', 'velocity_percent'):
        op.add_column('topic_issues',
            sa.Column('velocity_percent', sa.Float(), nullable=True, server_default='0.0'))
    if not column_exists('topic_issues', 'velocity_score'):
        op.add_column('topic_issues',
            sa.Column('velocity_score', sa.Float(), nullable=True, server_default='0.0'))
    if not column_exists('topic_issues', 'sentiment_distribution'):
        op.add_column('topic_issues',
            sa.Column('sentiment_distribution', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'weighted_sentiment_score'):
        op.add_column('topic_issues',
            sa.Column('weighted_sentiment_score', sa.Float(), nullable=True))
    if not column_exists('topic_issues', 'sentiment_index'):
        op.add_column('topic_issues',
            sa.Column('sentiment_index', sa.Float(), nullable=True))
    if not column_exists('topic_issues', 'emotion_distribution'):
        op.add_column('topic_issues',
            sa.Column('emotion_distribution', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'emotion_adjusted_severity'):
        op.add_column('topic_issues',
            sa.Column('emotion_adjusted_severity', sa.Float(), nullable=True))
    if not column_exists('topic_issues', 'priority_score'):
        op.add_column('topic_issues',
            sa.Column('priority_score', sa.Float(), nullable=True, server_default='0.0'))
    if not column_exists('topic_issues', 'priority_band'):
        op.add_column('topic_issues',
            sa.Column('priority_band', sa.String(length=20), nullable=True))
    if not column_exists('topic_issues', 'top_keywords'):
        op.add_column('topic_issues',
            sa.Column('top_keywords', postgresql.ARRAY(sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'top_sources'):
        op.add_column('topic_issues',
            sa.Column('top_sources', postgresql.ARRAY(sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'regions_impacted'):
        op.add_column('topic_issues',
            sa.Column('regions_impacted', postgresql.ARRAY(sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'entities_mentioned'):
        op.add_column('topic_issues',
            sa.Column('entities_mentioned', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'cluster_centroid_embedding'):
        op.add_column('topic_issues',
            sa.Column('cluster_centroid_embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if not column_exists('topic_issues', 'similarity_threshold'):
        op.add_column('topic_issues',
            sa.Column('similarity_threshold', sa.Float(), nullable=True, server_default='0.75'))
    if not column_exists('topic_issues', 'time_window_type'):
        op.add_column('topic_issues',
            sa.Column('time_window_type', sa.String(length=20), nullable=True))
    if not column_exists('topic_issues', 'volume_threshold'):
        op.add_column('topic_issues',
            sa.Column('volume_threshold', sa.Integer(), nullable=True, server_default='50'))
    if not column_exists('topic_issues', 'velocity_threshold'):
        op.add_column('topic_issues',
            sa.Column('velocity_threshold', sa.Float(), nullable=True, server_default='3.0'))
    if not column_exists('topic_issues', 'is_active'):
        op.add_column('topic_issues',
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    if not column_exists('topic_issues', 'is_archived'):
        op.add_column('topic_issues',
            sa.Column('is_archived', sa.Boolean(), nullable=True, server_default='false'))
    if not column_exists('topic_issues', 'updated_at'):
        op.add_column('topic_issues',
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')))
    
    # Add foreign key for primary_topic_key (if column exists and constraint doesn't)
    if column_exists('topic_issues', 'primary_topic_key'):
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        fks = [fk['name'] for fk in inspector.get_foreign_keys('topic_issues')]
        if 'fk_topic_issues_primary_topic' not in fks:
            op.create_foreign_key(
                'fk_topic_issues_primary_topic',
                'topic_issues', 'topics',
                ['primary_topic_key'], ['topic_key']
            )
    
    # Update issue_slug to be UNIQUE (not just per topic)
    # Check if old constraint exists and new one doesn't
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = [c['name'] for c in inspector.get_unique_constraints('topic_issues')]
    if 'uq_topic_issue' in constraints and 'uq_topic_issues_issue_slug' not in constraints:
        op.drop_constraint('uq_topic_issue', 'topic_issues', type_='unique')
        op.create_unique_constraint('uq_topic_issues_issue_slug', 'topic_issues', ['issue_slug'])
    elif 'uq_topic_issues_issue_slug' not in constraints:
        # New constraint doesn't exist, create it
        op.create_unique_constraint('uq_topic_issues_issue_slug', 'topic_issues', ['issue_slug'])
    
    # ============================================
    # 3. Create issue_mentions table (Junction: issue ↔ mentions)
    # ============================================
    if not table_exists('issue_mentions'):
        op.create_table('issue_mentions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mention_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('topic_key', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['issue_id'], ['topic_issues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mention_id'], ['sentiment_data.entry_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('issue_id', 'mention_id', name='uq_issue_mention')
        )
        op.create_index('idx_issue_mentions_issue', 'issue_mentions', ['issue_id'])
        op.create_index('idx_issue_mentions_mention', 'issue_mentions', ['mention_id'])
        op.create_index('idx_issue_mentions_topic', 'issue_mentions', ['topic_key'])
    
    # ============================================
    # 4. Create topic_issue_links table (Many-to-many: topic ↔ issue)
    # ============================================
    if not table_exists('topic_issue_links'):
        op.create_table('topic_issue_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('topic_key', sa.String(length=100), nullable=False),
        sa.Column('issue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_issues', sa.Integer(), nullable=True, server_default='20'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['topic_key'], ['topics.topic_key'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['issue_id'], ['topic_issues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_key', 'issue_id', name='uq_topic_issue_link')
        )
        op.create_index('idx_topic_issue_links_topic', 'topic_issue_links', ['topic_key'])
        op.create_index('idx_topic_issue_links_issue', 'topic_issue_links', ['issue_id'])
    
    # ============================================
    # 5. Create sentiment_aggregations table
    # ============================================
    if not table_exists('sentiment_aggregations'):
        op.create_table('sentiment_aggregations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregation_type', sa.String(length=50), nullable=False),
        sa.Column('aggregation_key', sa.String(length=200), nullable=False),
        sa.Column('time_window', sa.String(length=20), nullable=False),
        sa.Column('weighted_sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_index', sa.Float(), nullable=True),
        sa.Column('sentiment_distribution', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('emotion_distribution', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('emotion_adjusted_severity', sa.Float(), nullable=True),
        sa.Column('mention_count', sa.Integer(), nullable=True),
        sa.Column('total_influence_weight', sa.Float(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aggregation_type', 'aggregation_key', 'time_window', name='uq_sentiment_aggregation')
        )
        op.create_index('idx_sentiment_agg_type_key', 'sentiment_aggregations', ['aggregation_type', 'aggregation_key'])
        op.create_index('idx_sentiment_agg_time', 'sentiment_aggregations', ['calculated_at'])
    
    # ============================================
    # 6. Create sentiment_trends table
    # ============================================
    if not table_exists('sentiment_trends'):
        op.create_table('sentiment_trends',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregation_type', sa.String(length=50), nullable=False),
        sa.Column('aggregation_key', sa.String(length=200), nullable=False),
        sa.Column('time_window', sa.String(length=20), nullable=False),
        sa.Column('current_sentiment_index', sa.Float(), nullable=True),
        sa.Column('previous_sentiment_index', sa.Float(), nullable=True),
        sa.Column('trend_direction', sa.String(length=20), nullable=True),
        sa.Column('trend_magnitude', sa.Float(), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('previous_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('previous_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index('idx_sentiment_trends_type_key', 'sentiment_trends', ['aggregation_type', 'aggregation_key'])
        op.create_index('idx_sentiment_trends_time', 'sentiment_trends', ['calculated_at'])
    
    # ============================================
    # 7. Create topic_sentiment_baselines table
    # ============================================
    if not table_exists('topic_sentiment_baselines'):
        op.create_table('topic_sentiment_baselines',
        sa.Column('topic_key', sa.String(length=100), nullable=False),
        sa.Column('baseline_sentiment_index', sa.Float(), nullable=True),
        sa.Column('baseline_calculated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('lookback_days', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('sample_size', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['topic_key'], ['topics.topic_key']),
        sa.PrimaryKeyConstraint('topic_key')
        )
    
    # ============================================
    # 8. Add indexes for processing status (for efficient concurrent processing)
    # ============================================
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_sentiment_indexes = [idx['name'] for idx in inspector.get_indexes('sentiment_data')]
    
    if 'idx_sentiment_data_processing_status' not in existing_sentiment_indexes:
        op.create_index('idx_sentiment_data_processing_status', 'sentiment_data', ['processing_status'])
    
    if 'idx_sentiment_data_processing_pending' not in existing_sentiment_indexes:
        # Partial index for pending records (most efficient)
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_sentiment_data_processing_pending 
            ON sentiment_data(entry_id) 
            WHERE processing_status = 'pending' AND sentiment_label IS NULL
        """)
    
    if 'idx_sentiment_data_processing_time' not in existing_sentiment_indexes:
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_sentiment_data_processing_time 
            ON sentiment_data(processing_started_at) 
            WHERE processing_status = 'processing'
        """)
    
    # ============================================
    # 9. Add indexes to enhanced topic_issues table
    # ============================================
    existing_topic_issues_indexes = [idx['name'] for idx in inspector.get_indexes('topic_issues')]
    
    if 'idx_topic_issues_topic' not in existing_topic_issues_indexes and column_exists('topic_issues', 'primary_topic_key'):
        op.create_index('idx_topic_issues_topic', 'topic_issues', ['primary_topic_key'])
    if 'idx_topic_issues_state' not in existing_topic_issues_indexes and column_exists('topic_issues', 'state'):
        op.create_index('idx_topic_issues_state', 'topic_issues', ['state'])
    if 'idx_topic_issues_priority' not in existing_topic_issues_indexes and column_exists('topic_issues', 'priority_score'):
        op.create_index('idx_topic_issues_priority', 'topic_issues', ['priority_score'], postgresql_ops={'priority_score': 'DESC'})
    if 'idx_topic_issues_active' not in existing_topic_issues_indexes and column_exists('topic_issues', 'is_active'):
        op.create_index('idx_topic_issues_active', 'topic_issues', ['is_active', 'state'])
    if 'idx_topic_issues_time' not in existing_topic_issues_indexes and column_exists('topic_issues', 'start_time'):
        op.create_index('idx_topic_issues_time', 'topic_issues', ['start_time', 'last_activity'])


def downgrade() -> None:
    """Downgrade schema - remove all new tables and columns."""
    
    # Helper to check if index exists
    def index_exists(table_name: str, index_name: str) -> bool:
        try:
            bind = op.get_bind()
            inspector = sa.inspect(bind)
            indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
            return index_name in indexes
        except Exception:
            return False
    
    # Drop processing status indexes (with existence check)
    op.execute("DROP INDEX IF EXISTS idx_sentiment_data_processing_time")
    op.execute("DROP INDEX IF EXISTS idx_sentiment_data_processing_pending")
    if index_exists('sentiment_data', 'idx_sentiment_data_processing_status'):
        op.drop_index('idx_sentiment_data_processing_status', table_name='sentiment_data')
    
    # Drop topic_issues indexes
    op.drop_index('idx_topic_issues_time', table_name='topic_issues')
    op.drop_index('idx_topic_issues_active', table_name='topic_issues')
    op.drop_index('idx_topic_issues_priority', table_name='topic_issues')
    op.drop_index('idx_topic_issues_state', table_name='topic_issues')
    op.drop_index('idx_topic_issues_topic', table_name='topic_issues')
    
    # Drop new tables
    op.drop_table('topic_sentiment_baselines')
    op.drop_index('idx_sentiment_trends_time', table_name='sentiment_trends')
    op.drop_index('idx_sentiment_trends_type_key', table_name='sentiment_trends')
    op.drop_table('sentiment_trends')
    op.drop_index('idx_sentiment_agg_time', table_name='sentiment_aggregations')
    op.drop_index('idx_sentiment_agg_type_key', table_name='sentiment_aggregations')
    op.drop_table('sentiment_aggregations')
    op.drop_index('idx_topic_issue_links_issue', table_name='topic_issue_links')
    op.drop_index('idx_topic_issue_links_topic', table_name='topic_issue_links')
    op.drop_table('topic_issue_links')
    op.drop_index('idx_issue_mentions_topic', table_name='issue_mentions')
    op.drop_index('idx_issue_mentions_mention', table_name='issue_mentions')
    op.drop_index('idx_issue_mentions_issue', table_name='issue_mentions')
    op.drop_table('issue_mentions')
    
    # Revert topic_issues changes
    op.drop_constraint('uq_topic_issues_issue_slug', 'topic_issues', type_='unique')
    op.create_unique_constraint('uq_topic_issue', 'topic_issues', ['topic_key', 'issue_slug'])
    op.drop_constraint('fk_topic_issues_primary_topic', 'topic_issues', type_='foreignkey')
    
    # Drop columns from topic_issues
    op.drop_column('topic_issues', 'updated_at')
    op.drop_column('topic_issues', 'is_archived')
    op.drop_column('topic_issues', 'is_active')
    op.drop_column('topic_issues', 'velocity_threshold')
    op.drop_column('topic_issues', 'volume_threshold')
    op.drop_column('topic_issues', 'time_window_type')
    op.drop_column('topic_issues', 'similarity_threshold')
    op.drop_column('topic_issues', 'cluster_centroid_embedding')
    op.drop_column('topic_issues', 'entities_mentioned')
    op.drop_column('topic_issues', 'regions_impacted')
    op.drop_column('topic_issues', 'top_sources')
    op.drop_column('topic_issues', 'top_keywords')
    op.drop_column('topic_issues', 'priority_band')
    op.drop_column('topic_issues', 'priority_score')
    op.drop_column('topic_issues', 'emotion_adjusted_severity')
    op.drop_column('topic_issues', 'emotion_distribution')
    op.drop_column('topic_issues', 'sentiment_index')
    op.drop_column('topic_issues', 'weighted_sentiment_score')
    op.drop_column('topic_issues', 'sentiment_distribution')
    op.drop_column('topic_issues', 'velocity_score')
    op.drop_column('topic_issues', 'velocity_percent')
    op.drop_column('topic_issues', 'volume_previous_window')
    op.drop_column('topic_issues', 'volume_current_window')
    op.drop_column('topic_issues', 'resolved_at')
    op.drop_column('topic_issues', 'last_activity')
    op.drop_column('topic_issues', 'start_time')
    op.drop_column('topic_issues', 'status')
    op.drop_column('topic_issues', 'state')
    op.drop_column('topic_issues', 'primary_topic_key')
    op.drop_column('topic_issues', 'issue_title')
    
    # Drop indexes for processing status
    op.drop_index('idx_sentiment_data_processing_time', table_name='sentiment_data')
    op.execute("DROP INDEX IF EXISTS idx_sentiment_data_processing_pending")
    op.drop_index('idx_sentiment_data_processing_status', table_name='sentiment_data')
    
    # Drop columns from sentiment_data
    op.drop_column('sentiment_data', 'processing_error')
    op.drop_column('sentiment_data', 'processing_completed_at')
    op.drop_column('sentiment_data', 'processing_started_at')
    op.drop_column('sentiment_data', 'processing_status')
    op.drop_column('sentiment_data', 'confidence_weight')
    op.drop_column('sentiment_data', 'influence_weight')
    op.drop_column('sentiment_data', 'emotion_distribution')
    op.drop_column('sentiment_data', 'emotion_score')
    op.drop_column('sentiment_data', 'emotion_label')

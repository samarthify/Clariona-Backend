"""create topics tables

Revision ID: b2c3d4e5f6a7
Revises: a764cd54ae31
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a764cd54ae31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create topics tables."""
    
    # ============================================
    # 1. Topics Master Table
    # ============================================
    op.create_table('topics',
        sa.Column('topic_key', sa.String(length=100), nullable=False),
        sa.Column('topic_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('topic_key')
    )
    
    # ============================================
    # 2. Topic Issues Table
    # ============================================
    op.create_table('topic_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('topic_key', sa.String(length=100), nullable=False),
        sa.Column('issue_slug', sa.String(length=200), nullable=False),
        sa.Column('issue_label', sa.String(length=500), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_issues', sa.Integer(), nullable=True, server_default='20'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['topic_key'], ['topics.topic_key'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_key', 'issue_slug', name='uq_topic_issue'),
        sa.CheckConstraint('mention_count >= 0', name='check_mention_count_positive')
    )
    op.create_index('idx_topic_issues_topic_key', 'topic_issues', ['topic_key'])
    op.create_index('idx_topic_issues_issue_slug', 'topic_issues', ['issue_slug'])
    op.create_index('idx_topic_issues_mention_count', 'topic_issues', ['topic_key', 'mention_count'], postgresql_ops={'mention_count': 'DESC'})
    op.create_index('idx_topic_issues_topic_updated', 'topic_issues', ['topic_key', 'last_updated'], postgresql_ops={'last_updated': 'DESC'})
    
    # ============================================
    # 3. Mention Topics Junction Table
    # ============================================
    op.create_table('mention_topics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mention_id', sa.Integer(), nullable=False),
        sa.Column('topic_key', sa.String(length=100), nullable=False),
        sa.Column('topic_confidence', sa.Float(), nullable=False),
        sa.Column('keyword_score', sa.Float(), nullable=True),
        sa.Column('embedding_score', sa.Float(), nullable=True),
        sa.Column('issue_slug', sa.String(length=200), nullable=True),
        sa.Column('issue_label', sa.String(length=500), nullable=True),
        sa.Column('issue_confidence', sa.Float(), nullable=True),
        sa.Column('issue_keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['mention_id'], ['sentiment_data.entry_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_key'], ['topics.topic_key']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mention_id', 'topic_key', name='uq_mention_topic'),
        sa.CheckConstraint('topic_confidence >= 0.0 AND topic_confidence <= 1.0', name='check_confidence_range')
    )
    op.create_index('idx_mention_topics_mention_id', 'mention_topics', ['mention_id'])
    op.create_index('idx_mention_topics_created_at', 'mention_topics', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_mention_topics_topic_key', 'mention_topics', ['topic_key'])
    op.create_index('idx_mention_topics_topic_confidence', 'mention_topics', ['topic_key', 'topic_confidence'], postgresql_ops={'topic_confidence': 'DESC'})
    op.create_index('idx_mention_topics_issue_slug', 'mention_topics', ['issue_slug'], postgresql_where=sa.text('issue_slug IS NOT NULL'))
    op.create_index('idx_mention_topics_topic_mention', 'mention_topics', ['topic_key', 'mention_id', 'topic_confidence'], postgresql_ops={'topic_confidence': 'DESC'})
    
    # ============================================
    # 4. Owner Configs Table
    # ============================================
    op.create_table('owner_configs',
        sa.Column('owner_key', sa.String(length=100), nullable=False),
        sa.Column('owner_name', sa.String(length=200), nullable=False),
        sa.Column('owner_type', sa.String(length=50), nullable=True),
        sa.Column('topics', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('priority_topics', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('config_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('owner_key')
    )
    op.create_index('idx_owner_configs_topics', 'owner_configs', ['topics'], postgresql_using='gin')


def downgrade() -> None:
    """Downgrade schema - drop topics tables."""
    
    # Drop in reverse order (respecting foreign key constraints)
    op.drop_index('idx_owner_configs_topics', table_name='owner_configs')
    op.drop_table('owner_configs')
    
    op.drop_index('idx_mention_topics_topic_mention', table_name='mention_topics')
    op.drop_index('idx_mention_topics_issue_slug', table_name='mention_topics')
    op.drop_index('idx_mention_topics_topic_confidence', table_name='mention_topics')
    op.drop_index('idx_mention_topics_topic_key', table_name='mention_topics')
    op.drop_index('idx_mention_topics_created_at', table_name='mention_topics')
    op.drop_index('idx_mention_topics_mention_id', table_name='mention_topics')
    op.drop_table('mention_topics')
    
    op.drop_index('idx_topic_issues_topic_updated', table_name='topic_issues')
    op.drop_index('idx_topic_issues_mention_count', table_name='topic_issues')
    op.drop_index('idx_topic_issues_issue_slug', table_name='topic_issues')
    op.drop_index('idx_topic_issues_topic_key', table_name='topic_issues')
    op.drop_table('topic_issues')
    
    op.drop_table('topics')

















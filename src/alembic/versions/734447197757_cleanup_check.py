"""cleanup_check

Revision ID: 734447197757
Revises: add_sent_idx
Create Date: 2026-01-06 11:32:30.889662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '734447197757'
down_revision: Union[str, None] = 'add_sent_idx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop obsolete tables using CASCADE to handle FK dependencies
    tables_to_drop = [
        'escalation_timers',
        'notifications',
        'reports',
        'file_uploads',
        'user_dashboard_preferences',
        'mda_interactions',
        'widget_definitions',
        'tag_assignments',
        'tags',
        'security_settings',
        'user_preferences',
        'role_module_permissions',
        'role_dashboard_access',
        'dashboard_configs',
        'notification_queue',
        'alerts',
        'notification_settings',
        'notes',
        'checklists',
        'report_templates',
        'feedback_attachments',
        'feedback_comments',
        'feedback_submissions',
        'escalations',
        'role_feature_permissions',
        'audit_logs',
        'asset_library',
        'user_role_assignments',
        'role_topic_filters',
        'alert_rules',
        'ndcpi_roles',
    ]
    
    from sqlalchemy import text
    conn = op.get_bind()
    for table in tables_to_drop:
        try:
            conn.execute(text(f'DROP TABLE IF EXISTS {table} CASCADE'))
        except Exception as e:
            print(f"Warning: Could not drop table {table}: {e}")
    
    # Clean orphaned data before adding FK constraints
    # Delete user_system_usage records that reference non-existent users
    conn.execute(text('''
        DELETE FROM user_system_usage 
        WHERE user_id NOT IN (SELECT id FROM users)
    '''))
    
    # Delete configuration_audit_log records that reference non-existent users
    conn.execute(text('''
        DELETE FROM configuration_audit_log 
        WHERE changed_by IS NOT NULL 
        AND changed_by NOT IN (SELECT id FROM users)
    '''))
    
    # Delete system_configurations records that reference non-existent users  
    conn.execute(text('''
        UPDATE system_configurations 
        SET updated_by = NULL 
        WHERE updated_by IS NOT NULL 
        AND updated_by NOT IN (SELECT id FROM users)
    '''))
    
    # Continue with schema modifications
    op.create_foreign_key(None, 'configuration_audit_log', 'users', ['changed_by'], ['id'])
    op.alter_column('email_configurations', 'recipients',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.JSON(),
               existing_nullable=True)
    op.create_index(op.f('ix_email_configurations_id'), 'email_configurations', ['id'], unique=False)
    op.create_index(op.f('ix_email_configurations_user_id'), 'email_configurations', ['user_id'], unique=False)
    op.drop_constraint(op.f('issue_mentions_issue_id_fkey'), 'issue_mentions', type_='foreignkey')
    op.drop_constraint(op.f('issue_mentions_mention_id_fkey'), 'issue_mentions', type_='foreignkey')
    op.create_foreign_key(None, 'issue_mentions', 'topic_issues', ['issue_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'issue_mentions', 'sentiment_data', ['mention_id'], ['entry_id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'mention_topics', 'sentiment_data', ['mention_id'], ['entry_id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'mention_topics', 'topics', ['topic_key'], ['topic_key'])
    op.alter_column('sentiment_data', 'location_label',
               existing_type=sa.VARCHAR(length=255),
               comment=None,
               existing_comment='Geographic location label (e.g., Nigeria, Lagos, International)',
               existing_nullable=True)
    op.alter_column('sentiment_data', 'location_confidence',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment=None,
               existing_comment='Confidence score for location classification (0.0 to 1.0)',
               existing_nullable=True)
    op.alter_column('sentiment_data', 'issue_label',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=True)
    op.alter_column('sentiment_data', 'issue_slug',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=True)
    op.alter_column('sentiment_data', 'issue_keywords',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.JSON(),
               existing_nullable=True)
    op.drop_index(op.f('idx_sentiment_data_created_at'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_issue_created'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_issue_slug'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_ministry_created'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_platform'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_processing_pending'), table_name='sentiment_data', postgresql_where="(((processing_status)::text = 'pending'::text) AND (sentiment_label IS NULL))")
    op.drop_index(op.f('idx_sentiment_data_run_timestamp'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_sentiment_created'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_user_id'), table_name='sentiment_data')
    op.drop_index(op.f('idx_sentiment_data_user_platform_date'), table_name='sentiment_data')
    op.drop_index(op.f('ix_sentiment_data_url_unique'), table_name='sentiment_data', postgresql_where='(url IS NOT NULL)')
    op.create_index('ix_sentiment_data_platform', 'sentiment_data', ['platform'], unique=False)
    op.create_index(op.f('ix_sentiment_data_processing_status'), 'sentiment_data', ['processing_status'], unique=False)
    op.create_index(op.f('ix_sentiment_data_run_timestamp'), 'sentiment_data', ['run_timestamp'], unique=False)
    op.create_index(op.f('ix_sentiment_data_user_id'), 'sentiment_data', ['user_id'], unique=False)
    op.alter_column('sentiment_embeddings', 'embedding',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.JSON(),
               existing_nullable=True)
    op.drop_index(op.f('idx_sentiment_embeddings_entry_id'), table_name='sentiment_embeddings')
    op.drop_index(op.f('idx_sentiment_embeddings_model'), table_name='sentiment_embeddings')
    op.drop_constraint(op.f('sentiment_embeddings_entry_id_fkey'), 'sentiment_embeddings', type_='foreignkey')
    op.create_foreign_key(None, 'sentiment_embeddings', 'sentiment_data', ['entry_id'], ['entry_id'])
    op.create_foreign_key(None, 'system_configurations', 'users', ['updated_by'], ['id'])
    op.alter_column('target_individual_configurations', 'query_variations',
               existing_type=postgresql.JSONB(astext_type=sa.Text()),
               type_=sa.JSON(),
               existing_nullable=False)
    op.create_index(op.f('ix_target_individual_configurations_id'), 'target_individual_configurations', ['id'], unique=False)
    op.create_index(op.f('ix_target_individual_configurations_user_id'), 'target_individual_configurations', ['user_id'], unique=False)
    op.drop_index(op.f('idx_topic_issue_links_is_primary'), table_name='topic_issue_links')
    op.drop_constraint(op.f('topic_issue_links_topic_key_fkey'), 'topic_issue_links', type_='foreignkey')
    op.drop_constraint(op.f('topic_issue_links_issue_id_fkey'), 'topic_issue_links', type_='foreignkey')
    op.create_foreign_key(None, 'topic_issue_links', 'topics', ['topic_key'], ['topic_key'], ondelete='CASCADE')
    op.create_foreign_key(None, 'topic_issue_links', 'topic_issues', ['issue_id'], ['id'], ondelete='CASCADE')
    op.drop_column('topic_issue_links', 'is_primary')
    op.create_index('idx_topic_issues_active', 'topic_issues', ['is_active', 'state'], unique=False)
    op.create_index('idx_topic_issues_priority', 'topic_issues', ['priority_score'], unique=False)
    op.create_index('idx_topic_issues_state', 'topic_issues', ['state'], unique=False)
    op.create_index('idx_topic_issues_time', 'topic_issues', ['start_time', 'last_activity'], unique=False)
    op.create_index('idx_topic_issues_topic', 'topic_issues', ['primary_topic_key'], unique=False)
    op.create_foreign_key(None, 'topic_issues', 'topics', ['topic_key'], ['topic_key'], ondelete='CASCADE')
    op.create_foreign_key(None, 'topic_issues', 'topics', ['primary_topic_key'], ['topic_key'])
    op.create_foreign_key(None, 'topic_sentiment_baselines', 'topics', ['topic_key'], ['topic_key'])
    op.drop_index(op.f('idx_topics_keyword_groups'), table_name='topics', postgresql_using='gin')
    op.create_index(op.f('ix_user_system_usage_timestamp'), 'user_system_usage', ['timestamp'], unique=False)
    op.create_index(op.f('ix_user_system_usage_user_id'), 'user_system_usage', ['user_id'], unique=False)
    op.create_foreign_key(None, 'user_system_usage', 'users', ['user_id'], ['id'])
    op.alter_column('users', 'name',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=200),
               existing_nullable=True)
    op.drop_index(op.f('idx_users_email'), table_name='users')
    op.drop_index(op.f('idx_users_id'), table_name='users')
    op.drop_constraint(op.f('users_email_key'), 'users', type_='unique')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_unique_constraint(op.f('users_email_key'), 'users', ['email'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('idx_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('idx_users_email'), 'users', ['email'], unique=False)
    op.alter_column('users', 'name',
               existing_type=sa.String(length=200),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)
    op.drop_constraint(None, 'user_system_usage', type_='foreignkey')
    op.drop_index(op.f('ix_user_system_usage_user_id'), table_name='user_system_usage')
    op.drop_index(op.f('ix_user_system_usage_timestamp'), table_name='user_system_usage')
    op.create_index(op.f('idx_topics_keyword_groups'), 'topics', ['keyword_groups'], unique=False, postgresql_using='gin')
    op.drop_constraint(None, 'topic_sentiment_baselines', type_='foreignkey')
    op.drop_constraint(None, 'topic_issues', type_='foreignkey')
    op.drop_constraint(None, 'topic_issues', type_='foreignkey')
    op.drop_index('idx_topic_issues_topic', table_name='topic_issues')
    op.drop_index('idx_topic_issues_time', table_name='topic_issues')
    op.drop_index('idx_topic_issues_state', table_name='topic_issues')
    op.drop_index('idx_topic_issues_priority', table_name='topic_issues')
    op.drop_index('idx_topic_issues_active', table_name='topic_issues')
    op.add_column('topic_issue_links', sa.Column('is_primary', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'topic_issue_links', type_='foreignkey')
    op.drop_constraint(None, 'topic_issue_links', type_='foreignkey')
    op.create_foreign_key(op.f('topic_issue_links_issue_id_fkey'), 'topic_issue_links', 'topic_issues', ['issue_id'], ['id'], onupdate='CASCADE', ondelete='RESTRICT')
    op.create_foreign_key(op.f('topic_issue_links_topic_key_fkey'), 'topic_issue_links', 'topics', ['topic_key'], ['topic_key'], onupdate='CASCADE', ondelete='RESTRICT')
    op.create_index(op.f('idx_topic_issue_links_is_primary'), 'topic_issue_links', ['is_primary'], unique=False)
    op.drop_index(op.f('ix_target_individual_configurations_user_id'), table_name='target_individual_configurations')
    op.drop_index(op.f('ix_target_individual_configurations_id'), table_name='target_individual_configurations')
    op.alter_column('target_individual_configurations', 'query_variations',
               existing_type=sa.JSON(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=False)
    op.drop_constraint(None, 'system_configurations', type_='foreignkey')
    op.drop_constraint(None, 'sentiment_embeddings', type_='foreignkey')
    op.create_foreign_key(op.f('sentiment_embeddings_entry_id_fkey'), 'sentiment_embeddings', 'sentiment_data', ['entry_id'], ['entry_id'], ondelete='CASCADE')
    op.create_index(op.f('idx_sentiment_embeddings_model'), 'sentiment_embeddings', ['embedding_model'], unique=False)
    op.create_index(op.f('idx_sentiment_embeddings_entry_id'), 'sentiment_embeddings', ['entry_id'], unique=False)
    op.alter_column('sentiment_embeddings', 'embedding',
               existing_type=sa.JSON(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=True)
    op.drop_index(op.f('ix_sentiment_data_user_id'), table_name='sentiment_data')
    op.drop_index(op.f('ix_sentiment_data_run_timestamp'), table_name='sentiment_data')
    op.drop_index(op.f('ix_sentiment_data_processing_status'), table_name='sentiment_data')
    op.drop_index('ix_sentiment_data_platform', table_name='sentiment_data')
    op.create_index(op.f('ix_sentiment_data_url_unique'), 'sentiment_data', ['url'], unique=True, postgresql_where='(url IS NOT NULL)')
    op.create_index(op.f('idx_sentiment_data_user_platform_date'), 'sentiment_data', ['user_id', 'platform', 'published_at'], unique=False)
    op.create_index(op.f('idx_sentiment_data_user_id'), 'sentiment_data', ['user_id'], unique=False)
    op.create_index(op.f('idx_sentiment_data_sentiment_created'), 'sentiment_data', ['sentiment_label', 'created_at'], unique=False)
    op.create_index(op.f('idx_sentiment_data_run_timestamp'), 'sentiment_data', ['run_timestamp'], unique=False)
    op.create_index(op.f('idx_sentiment_data_processing_pending'), 'sentiment_data', ['processing_status'], unique=False, postgresql_where="(((processing_status)::text = 'pending'::text) AND (sentiment_label IS NULL))")
    op.create_index(op.f('idx_sentiment_data_platform'), 'sentiment_data', ['platform'], unique=False)
    op.create_index(op.f('idx_sentiment_data_ministry_created'), 'sentiment_data', ['ministry_hint', 'created_at'], unique=False)
    op.create_index(op.f('idx_sentiment_data_issue_slug'), 'sentiment_data', ['issue_slug'], unique=False)
    op.create_index(op.f('idx_sentiment_data_issue_created'), 'sentiment_data', ['issue_slug', 'created_at'], unique=False)
    op.create_index(op.f('idx_sentiment_data_created_at'), 'sentiment_data', ['created_at'], unique=False)
    op.alter_column('sentiment_data', 'issue_keywords',
               existing_type=sa.JSON(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=True)
    op.alter_column('sentiment_data', 'issue_slug',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               existing_nullable=True)
    op.alter_column('sentiment_data', 'issue_label',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               existing_nullable=True)
    op.alter_column('sentiment_data', 'location_confidence',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Confidence score for location classification (0.0 to 1.0)',
               existing_nullable=True)
    op.alter_column('sentiment_data', 'location_label',
               existing_type=sa.VARCHAR(length=255),
               comment='Geographic location label (e.g., Nigeria, Lagos, International)',
               existing_nullable=True)
    op.drop_constraint(None, 'mention_topics', type_='foreignkey')
    op.drop_constraint(None, 'mention_topics', type_='foreignkey')
    op.drop_constraint(None, 'issue_mentions', type_='foreignkey')
    op.drop_constraint(None, 'issue_mentions', type_='foreignkey')
    op.create_foreign_key(op.f('issue_mentions_mention_id_fkey'), 'issue_mentions', 'sentiment_data', ['mention_id'], ['entry_id'], onupdate='CASCADE', ondelete='RESTRICT')
    op.create_foreign_key(op.f('issue_mentions_issue_id_fkey'), 'issue_mentions', 'topic_issues', ['issue_id'], ['id'], onupdate='CASCADE', ondelete='RESTRICT')
    op.drop_index(op.f('ix_email_configurations_user_id'), table_name='email_configurations')
    op.drop_index(op.f('ix_email_configurations_id'), table_name='email_configurations')
    op.alter_column('email_configurations', 'recipients',
               existing_type=sa.JSON(),
               type_=postgresql.JSONB(astext_type=sa.Text()),
               existing_nullable=True)
    op.drop_constraint(None, 'configuration_audit_log', type_='foreignkey')
    op.create_table('alert_rules',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('rule_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('rule_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('rule_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=False),
    sa.Column('is_system', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('severity', sa.VARCHAR(length=20), server_default=sa.text("'warning'::character varying"), autoincrement=False, nullable=False),
    sa.Column('priority', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('sla_hours', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('default_assignee_role', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True, precision=6), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True, precision=6), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='alert_rules_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index(op.f('alert_rules_rule_type_idx'), 'alert_rules', ['rule_type'], unique=False)
    op.create_index(op.f('alert_rules_rule_key_key'), 'alert_rules', ['rule_key'], unique=True)
    op.create_index(op.f('alert_rules_is_active_idx'), 'alert_rules', ['is_active'], unique=False)
    op.create_table('role_topic_filters',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('topic_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('is_priority', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['role_key'], ['ndcpi_roles.role_key'], name=op.f('role_topic_filters_role_key_fkey')),
    sa.ForeignKeyConstraint(['topic_key'], ['topics.topic_key'], name=op.f('role_topic_filters_topic_key_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('role_topic_filters_pkey')),
    sa.UniqueConstraint('role_key', 'topic_key', name=op.f('role_topic_filters_role_key_topic_key_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_role_topic_filters_topic_key'), 'role_topic_filters', ['topic_key'], unique=False)
    op.create_index(op.f('idx_role_topic_filters_role_key'), 'role_topic_filters', ['role_key'], unique=False)
    op.create_table('user_role_assignments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('is_primary', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('assigned_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('assigned_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], name=op.f('user_role_assignments_assigned_by_fkey')),
    sa.ForeignKeyConstraint(['role_key'], ['ndcpi_roles.role_key'], name=op.f('user_role_assignments_role_key_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('user_role_assignments_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('user_role_assignments_pkey')),
    sa.UniqueConstraint('user_id', 'role_key', name=op.f('user_role_assignments_user_id_role_key_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_user_role_assignments_user_id'), 'user_role_assignments', ['user_id'], unique=False)
    op.create_index(op.f('idx_user_role_assignments_role_key'), 'user_role_assignments', ['role_key'], unique=False)
    op.create_index(op.f('idx_user_role_assignments_is_primary'), 'user_role_assignments', ['is_primary'], unique=False)
    op.create_table('asset_library',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('asset_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('asset_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('category', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('file_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('file_path', sa.VARCHAR(length=1000), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('usage_count', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('last_used_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('folder_path', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
    sa.Column('is_reusable', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('is_template', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('is_public', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('access_control', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('asset_library_created_by_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('asset_library_pkey'))
    )
    op.create_index(op.f('idx_asset_library_is_reusable'), 'asset_library', ['is_reusable'], unique=False)
    op.create_index(op.f('idx_asset_library_category'), 'asset_library', ['category'], unique=False)
    op.create_index(op.f('idx_asset_library_asset_type'), 'asset_library', ['asset_type'], unique=False)
    op.create_table('audit_logs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('action_type', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('entity_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('entity_id', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('user_email', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('user_role', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('ip_address', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('user_agent', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('session_id', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'success'::character varying"), autoincrement=False, nullable=True),
    sa.Column('error_message', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('audit_logs_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('audit_logs_pkey'))
    )
    op.create_index(op.f('idx_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('idx_audit_logs_entity'), 'audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('idx_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('idx_audit_logs_action_type'), 'audit_logs', ['action_type'], unique=False)
    op.create_table('role_feature_permissions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('feature_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('feature_name', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('can_access', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['role_key'], ['ndcpi_roles.role_key'], name=op.f('role_feature_permissions_role_key_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('role_feature_permissions_pkey')),
    sa.UniqueConstraint('role_key', 'feature_key', name=op.f('role_feature_permissions_role_key_feature_key_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_role_feature_permissions_role_key'), 'role_feature_permissions', ['role_key'], unique=False)
    op.create_table('feedback_comments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('feedback_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('comment_type', sa.VARCHAR(length=50), server_default=sa.text("'comment'::character varying"), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('is_internal', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('feedback_comments_created_by_fkey')),
    sa.ForeignKeyConstraint(['feedback_id'], ['feedback_submissions.id'], name=op.f('feedback_comments_feedback_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('feedback_comments_pkey'))
    )
    op.create_index(op.f('idx_feedback_comments_feedback_id'), 'feedback_comments', ['feedback_id'], unique=False)
    op.create_index(op.f('idx_feedback_comments_created_by'), 'feedback_comments', ['created_by'], unique=False)
    op.create_table('escalations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('issue_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('mention_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('alert_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('priority', sa.VARCHAR(length=20), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'pending'::character varying"), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('escalated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('sla_deadline', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('acknowledged_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('resolved_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('assigned_to', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('assigned_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('owner_role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('source', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], name='escalations_assigned_by_fkey'),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], name='escalations_assigned_to_fkey'),
    sa.ForeignKeyConstraint(['mention_id'], ['sentiment_data.entry_id'], name='escalations_mention_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='escalations_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index(op.f('idx_escalations_status'), 'escalations', ['status'], unique=False)
    op.create_index(op.f('idx_escalations_sla_deadline'), 'escalations', ['sla_deadline'], unique=False)
    op.create_index(op.f('idx_escalations_priority'), 'escalations', ['priority'], unique=False)
    op.create_index(op.f('idx_escalations_assigned_to'), 'escalations', ['assigned_to'], unique=False)
    op.create_table('tag_assignments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('tag_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('entity_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('entity_id', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('assigned_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('assigned_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], name=op.f('tag_assignments_assigned_by_fkey')),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('tag_assignments_tag_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('tag_assignments_pkey')),
    sa.UniqueConstraint('tag_id', 'entity_type', 'entity_id', name=op.f('tag_assignments_tag_id_entity_type_entity_id_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_tag_assignments_entity'), 'tag_assignments', ['entity_type', 'entity_id'], unique=False)
    op.create_table('feedback_submissions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('summary', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('feedback_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'draft'::character varying"), autoincrement=False, nullable=True),
    sa.Column('submitted_by', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('submitted_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('reviewed_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('reviewed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('sector', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('ministry', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('topic_keys', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('priority', sa.VARCHAR(length=20), server_default=sa.text("'medium'::character varying"), autoincrement=False, nullable=True),
    sa.Column('is_public', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], name='feedback_submissions_reviewed_by_fkey'),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], name='feedback_submissions_submitted_by_fkey'),
    sa.PrimaryKeyConstraint('id', name='feedback_submissions_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index(op.f('idx_feedback_submissions_submitted_by'), 'feedback_submissions', ['submitted_by'], unique=False)
    op.create_index(op.f('idx_feedback_submissions_status'), 'feedback_submissions', ['status'], unique=False)
    op.create_index(op.f('idx_feedback_submissions_sector'), 'feedback_submissions', ['sector'], unique=False)
    op.create_index(op.f('idx_feedback_submissions_priority'), 'feedback_submissions', ['priority'], unique=False)
    op.create_table('feedback_attachments',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('feedback_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('file_name', sa.VARCHAR(length=500), autoincrement=False, nullable=False),
    sa.Column('file_path', sa.VARCHAR(length=1000), autoincrement=False, nullable=False),
    sa.Column('file_size', sa.BIGINT(), autoincrement=False, nullable=True),
    sa.Column('mime_type', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('file_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('transcribed_text', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('summary', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('uploaded_by', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('uploaded_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['feedback_id'], ['feedback_submissions.id'], name=op.f('feedback_attachments_feedback_id_fkey')),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('feedback_attachments_uploaded_by_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('feedback_attachments_pkey'))
    )
    op.create_index(op.f('idx_feedback_attachments_file_type'), 'feedback_attachments', ['file_type'], unique=False)
    op.create_index(op.f('idx_feedback_attachments_feedback_id'), 'feedback_attachments', ['feedback_id'], unique=False)
    op.create_table('report_templates',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('template_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('template_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('template_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('template_config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('is_default', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('is_public', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='report_templates_created_by_fkey'),
    sa.PrimaryKeyConstraint('id', name='report_templates_pkey'),
    sa.UniqueConstraint('template_key', name='report_templates_template_key_key', postgresql_include=[], postgresql_nulls_not_distinct=False),
    postgresql_ignore_search_path=False
    )
    op.create_index(op.f('idx_report_templates_template_type'), 'report_templates', ['template_type'], unique=False)
    op.create_index(op.f('idx_report_templates_role_key'), 'report_templates', ['role_key'], unique=False)
    op.create_table('ndcpi_roles',
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('role_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('department', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('role_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('role_key', name='ndcpi_roles_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index(op.f('idx_ndcpi_roles_role_type'), 'ndcpi_roles', ['role_type'], unique=False)
    op.create_index(op.f('idx_ndcpi_roles_is_active'), 'ndcpi_roles', ['is_active'], unique=False)
    op.create_table('checklists',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('checklist_type', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('items', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('assigned_to', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'in_progress'::character varying"), autoincrement=False, nullable=True),
    sa.Column('completed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('completed_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], name=op.f('checklists_assigned_to_fkey')),
    sa.ForeignKeyConstraint(['completed_by'], ['users.id'], name=op.f('checklists_completed_by_fkey')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('checklists_created_by_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('checklists_pkey'))
    )
    op.create_index(op.f('idx_checklists_status'), 'checklists', ['status'], unique=False)
    op.create_index(op.f('idx_checklists_checklist_type'), 'checklists', ['checklist_type'], unique=False)
    op.create_index(op.f('idx_checklists_assigned_to'), 'checklists', ['assigned_to'], unique=False)
    op.create_table('notes',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('entity_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('entity_id', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('note_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('is_private', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('notes_created_by_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('notes_pkey'))
    )
    op.create_index(op.f('idx_notes_entity'), 'notes', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('idx_notes_created_by'), 'notes', ['created_by'], unique=False)
    op.create_index(op.f('idx_notes_created_at'), 'notes', ['created_at'], unique=False)
    op.create_table('notification_settings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('email_enabled', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('push_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('sms_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('in_app_enabled', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('notify_on_alerts', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('notify_on_escalations', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('notify_on_feedback', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('notify_on_mentions', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('notify_on_reports', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('notification_frequency', sa.VARCHAR(length=20), server_default=sa.text("'realtime'::character varying"), autoincrement=False, nullable=True),
    sa.Column('quiet_hours_start', sa.VARCHAR(length=10), autoincrement=False, nullable=True),
    sa.Column('quiet_hours_end', sa.VARCHAR(length=10), autoincrement=False, nullable=True),
    sa.Column('min_priority', sa.VARCHAR(length=20), server_default=sa.text("'medium'::character varying"), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('notification_settings_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('notification_settings_pkey')),
    sa.UniqueConstraint('user_id', name=op.f('notification_settings_user_id_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_table('alerts',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('issue_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('issue_slug', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('topic_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('alert_rule_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('alert_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('severity', sa.VARCHAR(length=20), server_default=sa.text("'warning'::character varying"), autoincrement=False, nullable=False),
    sa.Column('priority', sa.VARCHAR(length=20), server_default=sa.text("'medium'::character varying"), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'triggered'::character varying"), autoincrement=False, nullable=False),
    sa.Column('triggered_at', postgresql.TIMESTAMP(timezone=True, precision=6), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False),
    sa.Column('acknowledged_at', postgresql.TIMESTAMP(timezone=True, precision=6), autoincrement=False, nullable=True),
    sa.Column('resolved_at', postgresql.TIMESTAMP(timezone=True, precision=6), autoincrement=False, nullable=True),
    sa.Column('dismissed_at', postgresql.TIMESTAMP(timezone=True, precision=6), autoincrement=False, nullable=True),
    sa.Column('sla_deadline', postgresql.TIMESTAMP(timezone=True, precision=6), autoincrement=False, nullable=True),
    sa.Column('owner_role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('region', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('issue_snapshot', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True, precision=6), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True, precision=6), server_default=sa.text('CURRENT_TIMESTAMP'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['alert_rule_id'], ['alert_rules.id'], name=op.f('alerts_alert_rule_id_fkey'), onupdate='CASCADE', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['issue_id'], ['topic_issues.id'], name=op.f('alerts_issue_id_fkey'), onupdate='CASCADE', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('alerts_pkey'))
    )
    op.create_index(op.f('alerts_triggered_at_idx'), 'alerts', ['triggered_at'], unique=False)
    op.create_index(op.f('alerts_topic_key_idx'), 'alerts', ['topic_key'], unique=False)
    op.create_index(op.f('alerts_status_idx'), 'alerts', ['status'], unique=False)
    op.create_index(op.f('alerts_priority_idx'), 'alerts', ['priority'], unique=False)
    op.create_index(op.f('alerts_issue_slug_idx'), 'alerts', ['issue_slug'], unique=False)
    op.create_index(op.f('alerts_issue_id_idx'), 'alerts', ['issue_id'], unique=False)
    op.create_index(op.f('alerts_alert_rule_id_idx'), 'alerts', ['alert_rule_id'], unique=False)
    op.create_table('notification_queue',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('notification_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('channel', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('recipient', sa.VARCHAR(length=500), autoincrement=False, nullable=False),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'pending'::character varying"), autoincrement=False, nullable=True),
    sa.Column('attempts', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('max_attempts', sa.INTEGER(), server_default=sa.text('3'), autoincrement=False, nullable=True),
    sa.Column('scheduled_for', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('sent_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('delivered_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('failed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('error_message', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('next_retry_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('notification_queue_pkey'))
    )
    op.create_index(op.f('idx_notification_queue_status'), 'notification_queue', ['status'], unique=False)
    op.create_index(op.f('idx_notification_queue_scheduled_for'), 'notification_queue', ['scheduled_for'], unique=False)
    op.create_index(op.f('idx_notification_queue_channel'), 'notification_queue', ['channel'], unique=False)
    op.create_table('dashboard_configs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('dashboard_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('is_default', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('is_public', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('is_template', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('layout_config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('widget_configs', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.Column('theme', sa.VARCHAR(length=20), server_default=sa.text("'light'::character varying"), autoincrement=False, nullable=True),
    sa.Column('layout_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('real_time_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('update_frequency', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('websocket_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('version', sa.INTEGER(), server_default=sa.text('1'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='dashboard_configs_created_by_fkey'),
    sa.ForeignKeyConstraint(['role_key'], ['ndcpi_roles.role_key'], name='dashboard_configs_role_key_fkey'),
    sa.PrimaryKeyConstraint('id', name='dashboard_configs_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index(op.f('idx_dashboard_configs_role_key'), 'dashboard_configs', ['role_key'], unique=False)
    op.create_index(op.f('idx_dashboard_configs_is_default'), 'dashboard_configs', ['is_default'], unique=False)
    op.create_index(op.f('idx_dashboard_configs_dashboard_key'), 'dashboard_configs', ['dashboard_key'], unique=False)
    op.create_table('role_dashboard_access',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('dashboard_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('dashboard_name', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('is_primary', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('can_edit', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['role_key'], ['ndcpi_roles.role_key'], name=op.f('role_dashboard_access_role_key_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('role_dashboard_access_pkey')),
    sa.UniqueConstraint('role_key', 'dashboard_key', name=op.f('role_dashboard_access_role_key_dashboard_key_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_role_dashboard_access_role_key'), 'role_dashboard_access', ['role_key'], unique=False)
    op.create_index(op.f('idx_role_dashboard_access_is_primary'), 'role_dashboard_access', ['is_primary'], unique=False)
    op.create_table('role_module_permissions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('module_key', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('can_access', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('can_create', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('can_edit', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('can_delete', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('can_view', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['role_key'], ['ndcpi_roles.role_key'], name=op.f('role_module_permissions_role_key_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('role_module_permissions_pkey')),
    sa.UniqueConstraint('role_key', 'module_key', name=op.f('role_module_permissions_role_key_module_key_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_role_module_permissions_role_key'), 'role_module_permissions', ['role_key'], unique=False)
    op.create_table('user_preferences',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('theme', sa.VARCHAR(length=20), server_default=sa.text("'light'::character varying"), autoincrement=False, nullable=True),
    sa.Column('language', sa.VARCHAR(length=10), server_default=sa.text("'en'::character varying"), autoincrement=False, nullable=True),
    sa.Column('timezone', sa.VARCHAR(length=50), server_default=sa.text("'UTC'::character varying"), autoincrement=False, nullable=True),
    sa.Column('date_format', sa.VARCHAR(length=20), server_default=sa.text("'YYYY-MM-DD'::character varying"), autoincrement=False, nullable=True),
    sa.Column('time_format', sa.VARCHAR(length=20), server_default=sa.text("'24h'::character varying"), autoincrement=False, nullable=True),
    sa.Column('default_dashboard_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('dashboard_refresh_interval', sa.INTEGER(), server_default=sa.text('60'), autoincrement=False, nullable=True),
    sa.Column('region', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('currency', sa.VARCHAR(length=10), autoincrement=False, nullable=True),
    sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['default_dashboard_id'], ['dashboard_configs.id'], name=op.f('user_preferences_default_dashboard_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('user_preferences_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('user_preferences_pkey')),
    sa.UniqueConstraint('user_id', name=op.f('user_preferences_user_id_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_table('security_settings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('two_factor_enabled', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('two_factor_secret', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('two_factor_backup_codes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('password_changed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('password_expires_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('require_password_change', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('max_sessions', sa.INTEGER(), server_default=sa.text('5'), autoincrement=False, nullable=True),
    sa.Column('session_timeout_minutes', sa.INTEGER(), server_default=sa.text('60'), autoincrement=False, nullable=True),
    sa.Column('security_questions', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('last_login_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('last_login_ip', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('failed_login_attempts', sa.INTEGER(), server_default=sa.text('0'), autoincrement=False, nullable=True),
    sa.Column('account_locked_until', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('security_settings_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('security_settings_pkey')),
    sa.UniqueConstraint('user_id', name=op.f('security_settings_user_id_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_table('tags',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('tag_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('tag_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('tag_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('color', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('tags_pkey')),
    sa.UniqueConstraint('tag_key', name=op.f('tags_tag_key_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_tags_tag_type'), 'tags', ['tag_type'], unique=False)
    op.create_index(op.f('idx_tags_is_active'), 'tags', ['is_active'], unique=False)
    op.create_table('widget_definitions',
    sa.Column('widget_key', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
    sa.Column('widget_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('widget_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('category', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('icon', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('component_path', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
    sa.Column('default_width', sa.INTEGER(), server_default=sa.text('3'), autoincrement=False, nullable=True),
    sa.Column('default_height', sa.INTEGER(), server_default=sa.text('2'), autoincrement=False, nullable=True),
    sa.Column('min_width', sa.INTEGER(), server_default=sa.text('2'), autoincrement=False, nullable=True),
    sa.Column('min_height', sa.INTEGER(), server_default=sa.text('2'), autoincrement=False, nullable=True),
    sa.Column('max_width', sa.INTEGER(), server_default=sa.text('12'), autoincrement=False, nullable=True),
    sa.Column('max_height', sa.INTEGER(), server_default=sa.text('8'), autoincrement=False, nullable=True),
    sa.Column('config_schema', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('default_config', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('required_permissions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('available_for_roles', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('data_source_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('data_source_config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('widget_key', name=op.f('widget_definitions_pkey'))
    )
    op.create_index(op.f('idx_widget_definitions_widget_type'), 'widget_definitions', ['widget_type'], unique=False)
    op.create_index(op.f('idx_widget_definitions_is_active'), 'widget_definitions', ['is_active'], unique=False)
    op.create_index(op.f('idx_widget_definitions_category'), 'widget_definitions', ['category'], unique=False)
    op.create_table('mda_interactions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('feedback_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('issue_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('interaction_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('mda_name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('mda_contact', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'pending'::character varying"), autoincrement=False, nullable=True),
    sa.Column('responded_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('mda_interactions_created_by_fkey')),
    sa.ForeignKeyConstraint(['feedback_id'], ['feedback_submissions.id'], name=op.f('mda_interactions_feedback_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('mda_interactions_pkey'))
    )
    op.create_index(op.f('idx_mda_interactions_status'), 'mda_interactions', ['status'], unique=False)
    op.create_index(op.f('idx_mda_interactions_mda_name'), 'mda_interactions', ['mda_name'], unique=False)
    op.create_index(op.f('idx_mda_interactions_feedback_id'), 'mda_interactions', ['feedback_id'], unique=False)
    op.create_table('user_dashboard_preferences',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('dashboard_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('role_key', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('custom_layout_config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('custom_widget_configs', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('theme_preference', sa.VARCHAR(length=20), server_default=sa.text("'light'::character varying"), autoincrement=False, nullable=True),
    sa.Column('refresh_interval', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['dashboard_id'], ['dashboard_configs.id'], name=op.f('user_dashboard_preferences_dashboard_id_fkey')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('user_dashboard_preferences_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('user_dashboard_preferences_pkey')),
    sa.UniqueConstraint('user_id', 'dashboard_id', name=op.f('user_dashboard_preferences_user_id_dashboard_id_key'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('idx_user_dashboard_preferences_user_id'), 'user_dashboard_preferences', ['user_id'], unique=False)
    op.create_table('file_uploads',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('file_name', sa.VARCHAR(length=500), autoincrement=False, nullable=False),
    sa.Column('original_file_name', sa.VARCHAR(length=500), autoincrement=False, nullable=False),
    sa.Column('file_path', sa.VARCHAR(length=1000), autoincrement=False, nullable=False),
    sa.Column('file_size', sa.BIGINT(), autoincrement=False, nullable=False),
    sa.Column('mime_type', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('file_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('entity_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('entity_id', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('processing_status', sa.VARCHAR(length=50), server_default=sa.text("'pending'::character varying"), autoincrement=False, nullable=True),
    sa.Column('processed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('extracted_text', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('thumbnail_path', sa.VARCHAR(length=1000), autoincrement=False, nullable=True),
    sa.Column('uploaded_by', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('uploaded_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('is_public', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('access_control', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('file_uploads_uploaded_by_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('file_uploads_pkey'))
    )
    op.create_index(op.f('idx_file_uploads_uploaded_by'), 'file_uploads', ['uploaded_by'], unique=False)
    op.create_index(op.f('idx_file_uploads_processing_status'), 'file_uploads', ['processing_status'], unique=False)
    op.create_index(op.f('idx_file_uploads_file_type'), 'file_uploads', ['file_type'], unique=False)
    op.create_index(op.f('idx_file_uploads_entity'), 'file_uploads', ['entity_type', 'entity_id'], unique=False)
    op.create_table('reports',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('template_id', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('report_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'draft'::character varying"), autoincrement=False, nullable=True),
    sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True),
    sa.Column('generated_content', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('file_path', sa.VARCHAR(length=1000), autoincrement=False, nullable=True),
    sa.Column('generated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('generated_by', sa.UUID(), autoincrement=False, nullable=True),
    sa.Column('generation_time_seconds', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('data_start_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('data_end_date', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('topic_keys', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('is_public', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('shared_with', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('version', sa.INTEGER(), server_default=sa.text('1'), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['generated_by'], ['users.id'], name=op.f('reports_generated_by_fkey')),
    sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], name=op.f('reports_template_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('reports_pkey'))
    )
    op.create_index(op.f('idx_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('idx_reports_report_type'), 'reports', ['report_type'], unique=False)
    op.create_index(op.f('idx_reports_generated_by'), 'reports', ['generated_by'], unique=False)
    op.create_index(op.f('idx_reports_generated_at'), 'reports', ['generated_at'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
    sa.Column('message', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('notification_type', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.Column('priority', sa.VARCHAR(length=20), server_default=sa.text("'medium'::character varying"), autoincrement=False, nullable=True),
    sa.Column('entity_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('entity_id', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
    sa.Column('is_read', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('read_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('is_dismissed', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('dismissed_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('delivery_channels', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=True),
    sa.Column('sent_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('delivered_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('action_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
    sa.Column('action_label', sa.VARCHAR(length=100), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('notifications_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('notifications_pkey'))
    )
    op.create_index(op.f('idx_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('idx_notifications_notification_type'), 'notifications', ['notification_type'], unique=False)
    op.create_index(op.f('idx_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('idx_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_table('escalation_timers',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), autoincrement=False, nullable=False),
    sa.Column('escalation_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('timer_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    sa.Column('start_time', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('end_time', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('duration_seconds', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), server_default=sa.text('true'), autoincrement=False, nullable=True),
    sa.Column('is_expired', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('expired_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('alert_sent', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True),
    sa.Column('alert_sent_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['escalation_id'], ['escalations.id'], name=op.f('escalation_timers_escalation_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('escalation_timers_pkey'))
    )
    op.create_index(op.f('idx_escalation_timers_is_active'), 'escalation_timers', ['is_active'], unique=False)
    op.create_index(op.f('idx_escalation_timers_escalation_id'), 'escalation_timers', ['escalation_id'], unique=False)
    op.create_index(op.f('idx_escalation_timers_end_time'), 'escalation_timers', ['end_time'], unique=False)
    # ### end Alembic commands ###

"""add configuration tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create configuration management tables."""
    
    # Create configuration_schemas table
    op.create_table(
        'configuration_schemas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('schema_definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('default_values', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category')
    )
    op.create_index('ix_configuration_schemas_category', 'configuration_schemas', ['category'], unique=False)
    
    # Create system_configurations table
    op.create_table(
        'system_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('config_key', sa.String(length=255), nullable=False),
        sa.Column('config_value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('config_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', 'config_key', name='uq_category_config_key')
    )
    op.create_index('ix_system_configurations_category', 'system_configurations', ['category'], unique=False)
    op.create_index('ix_system_configurations_category_config_key', 'system_configurations', ['category', 'config_key'], unique=False)
    
    # Create configuration_audit_log table
    op.create_table(
        'configuration_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('config_key', sa.String(length=255), nullable=False),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_configuration_audit_log_category', 'configuration_audit_log', ['category'], unique=False)
    op.create_index('ix_configuration_audit_log_changed_at', 'configuration_audit_log', ['changed_at'], unique=False)


def downgrade() -> None:
    """Drop configuration management tables."""
    
    op.drop_index('ix_configuration_audit_log_changed_at', table_name='configuration_audit_log')
    op.drop_index('ix_configuration_audit_log_category', table_name='configuration_audit_log')
    op.drop_table('configuration_audit_log')
    
    op.drop_index('ix_system_configurations_category_config_key', table_name='system_configurations')
    op.drop_index('ix_system_configurations_category', table_name='system_configurations')
    op.drop_table('system_configurations')
    
    op.drop_index('ix_configuration_schemas_category', table_name='configuration_schemas')
    op.drop_table('configuration_schemas')













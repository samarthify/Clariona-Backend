"""Add owner_key to users for CrisisActionDispatcher fan-out

Revision ID: 20260309_04
Revises: 20260309_03
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260309_04"
down_revision: Union[str, None] = "20260309_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "users", "owner_key"):
        op.add_column(
            "users",
            sa.Column("owner_key", sa.String(100), nullable=True),
        )
        op.create_index(
            "idx_users_owner_key",
            "users",
            ["owner_key"],
            unique=False,
        )

    # Backfill using same logic as create_owner_key() in sync_users_to_owner_configs.py
    op.execute("""
        UPDATE users SET owner_key = CASE
            WHEN LOWER(COALESCE(role, '')) = 'president' THEN 'president'
            WHEN LOWER(COALESCE(role, '')) = 'agency' AND ministry IS NOT NULL AND TRIM(ministry) != ''
                THEN 'agency_' || LOWER(REPLACE(REPLACE(TRIM(ministry), ' ', '_'), '-', '_'))
            WHEN LOWER(COALESCE(role, '')) = 'agency'
                THEN 'agency_' || REPLACE(id::text, '-', '_')
            WHEN ministry IS NOT NULL AND TRIM(ministry) != ''
                THEN 'minister_' || LOWER(REPLACE(REPLACE(TRIM(ministry), ' ', '_'), '-', '_'))
            ELSE 'user_' || REPLACE(id::text, '-', '_')
        END
        WHERE owner_key IS NULL
    """)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("idx_users_owner_key", table_name="users")
    if _column_exists(bind, "users", "owner_key"):
        op.drop_column("users", "owner_key")

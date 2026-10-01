"""make_access_logs_user_id_nullable

Revision ID: 0002_nullable_user_id
Revises: 0001_initial
Create Date: 2026-09-30

Makes access_logs.user_id nullable so that failed logins by unknown
usernames (no matching user row) can still be logged for anomaly detection.
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_nullable_user_id'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('access_logs', 'user_id', nullable=True)


def downgrade() -> None:
    # Rows with NULL user_id must be deleted before reverting
    op.execute("DELETE FROM access_logs WHERE user_id IS NULL")
    op.alter_column('access_logs', 'user_id', nullable=False)

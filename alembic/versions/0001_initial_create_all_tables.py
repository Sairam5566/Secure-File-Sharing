"""create_all_tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-29

Creates users, files, and access_logs tables for PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(100), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # --- files ---
    op.create_table(
        'files',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('encrypted_path', sa.String(500), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('upload_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('blockchain_tx_hash', sa.String(66), nullable=True),
        sa.Column('blockchain_index', sa.Integer(), nullable=True),
    )
    op.create_index('ix_files_id', 'files', ['id'])
    op.create_index('ix_files_file_hash', 'files', ['file_hash'])
    op.create_index('ix_files_owner_not_deleted', 'files', ['owner_id', 'is_deleted'])

    # --- access_logs ---
    op.create_table(
        'access_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id'), nullable=True),
        sa.Column('access_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('access_status', sa.String(20), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('device_info', sa.String(500), nullable=True),
        sa.Column('action_type', sa.String(20), nullable=False),
        sa.Column('is_anomalous', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.create_index('ix_access_logs_id', 'access_logs', ['id'])
    op.create_index('ix_access_logs_access_time', 'access_logs', ['access_time'])
    op.create_index('ix_access_logs_user_time', 'access_logs', ['user_id', 'access_time'])
    op.create_index('ix_access_logs_action_time', 'access_logs', ['action_type', 'access_time'])


def downgrade() -> None:
    op.drop_table('access_logs')
    op.drop_table('files')
    op.drop_table('users')

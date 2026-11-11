"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-15 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Admin Authentication
    op.create_table(
        'admin_auth',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('single_row', sa.String(length=10), nullable=False, server_default='SINGLETON'),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('password_initialized', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('single_row')
    )

    # 2. Auth Sessions
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_auth.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_auth_sessions_session_token_hash', 'auth_sessions', ['session_token_hash'])

    # 3. Password Reset Tokens
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['admin_auth.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'])

    # 4. Login Attempts
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('attempted_username', sa.String(length=100), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_login_attempts_ip_address', 'login_attempts', ['ip_address'])

    # 5. Zoho Credentials
    op.create_table(
        'zoho_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.String(length=100), nullable=True),
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. OAuth States
    op.create_table(
        'oauth_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('state')
    )
    op.create_index('ix_oauth_states_state', 'oauth_states', ['state'])

    # 7. Upload Sessions
    op.create_table(
        'upload_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('upload_session_id', sa.String(length=64), nullable=False),
        sa.Column('total_rows', sa.Integer(), nullable=False),
        sa.Column('valid_rows', sa.Integer(), nullable=False),
        sa.Column('invalid_rows', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='IDLE'),
        sa.Column('mapping_snapshot', sa.Text(), nullable=True),
        sa.Column('selected_gst_report_id', sa.String(length=100), nullable=True),
        sa.Column('selected_nongst_report_id', sa.String(length=100), nullable=True),
        sa.Column('lock_version', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. Expense Records
    op.create_table(
        'expense_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('original_row_number', sa.Integer(), nullable=False),
        sa.Column('expense_date', sa.String(length=50), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gst_type', sa.String(length=20), nullable=True),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('project', sa.String(length=255), nullable=True),
        sa.Column('tax_type', sa.String(length=255), nullable=True),
        sa.Column('paid_through', sa.String(length=255), nullable=True),
        sa.Column('vendor_name', sa.String(length=255), nullable=True),
        sa.Column('expense_kind', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='VALID'),
        sa.Column('validation_errors', sa.Text(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('duplicate_reason', sa.String(length=255), nullable=True),
        sa.Column('zoho_status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('zoho_expense_id', sa.String(length=100), nullable=True),
        sa.Column('zoho_error', sa.Text(), nullable=True),
        sa.Column('destination_report_id', sa.String(length=100), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['upload_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. Audit Logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['upload_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('expense_records')
    op.drop_table('upload_sessions')
    op.drop_table('oauth_states')
    op.drop_table('zoho_credentials')
    op.drop_table('login_attempts')
    op.drop_index('ix_password_reset_tokens_token_hash', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_index('ix_auth_sessions_session_token_hash', table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_table('admin_auth')

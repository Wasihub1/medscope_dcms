"""prompt09_role_based_auth

Revision ID: b9e41d82f05a
Revises: a7d834bc912e
Create Date: 2026-11-11 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e41d82f05a'
down_revision: Union[str, None] = 'a7d834bc912e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add authentication & security columns to `staff`
    op.add_column('staff', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('staff', sa.Column('failed_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('staff', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('staff', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('staff', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Create `staff_roles` table for multi-role support per person
    op.create_table(
        'staff_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name='fk_staff_roles_staff_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id', 'role', name='uq_staff_roles_staff_id_role'),
    )
    op.create_index('ix_staff_roles_staff_id', 'staff_roles', ['staff_id'], unique=False)
    op.create_index('ix_staff_roles_role', 'staff_roles', ['role'], unique=False)

    # 3. Seed `staff_roles` from existing `staff` rows
    op.execute(
        """
        INSERT INTO staff_roles (staff_id, role, is_primary, created_at)
        SELECT id, role, true, NOW()
        FROM staff
        ON CONFLICT (staff_id, role) DO NOTHING
        """
    )

    # 4. Create `auth_sessions` table for server-side session management
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('acting_role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], name='fk_auth_sessions_staff_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auth_sessions_session_token_hash', 'auth_sessions', ['session_token_hash'], unique=True)
    op.create_index('ix_auth_sessions_staff_id', 'auth_sessions', ['staff_id'], unique=False)
    op.create_index('ix_auth_sessions_tenant_id', 'auth_sessions', ['tenant_id'], unique=False)
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'], unique=False)
    op.create_index('ix_auth_sessions_revoked_at', 'auth_sessions', ['revoked_at'], unique=False)


def downgrade() -> None:
    op.drop_table('auth_sessions')
    op.drop_table('staff_roles')
    op.drop_column('staff', 'password_changed_at')
    op.drop_column('staff', 'last_login_at')
    op.drop_column('staff', 'locked_at')
    op.drop_column('staff', 'failed_attempts')
    op.drop_column('staff', 'password_hash')

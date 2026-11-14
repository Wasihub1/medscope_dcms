"""prompt15_doctor_approvals: D22 doctor-side approval record

Autogenerate was reviewed by hand: the two unnamed foreign keys (staff.doctor_profile_id and
test_orders.assigned_doctor_id) got explicit names, because the rendered drop_constraint(None, ...)
in the downgrade would have failed. Purely additive: one new table and two nullable columns; no
existing row is changed.

Revision ID: c9a4e7b2d815
Revises: b7e3d91c5a24
Create Date: 2026-11-14 12:35:24.970748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9a4e7b2d815'
down_revision: Union[str, None] = 'b7e3d91c5a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('doctor_approvals',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=64), nullable=False),
    sa.Column('test_order_id', sa.Integer(), nullable=False),
    sa.Column('result_id', sa.Integer(), nullable=False),
    sa.Column('approval_rule', sa.String(length=50), nullable=False),
    sa.Column('doctor_id', sa.Integer(), nullable=False),
    sa.Column('doctor_name', sa.String(length=200), nullable=False),
    sa.Column('doctor_registration_no', sa.String(length=100), nullable=False),
    sa.Column('approved_by_user_id', sa.Integer(), nullable=False),
    sa.Column('approved_by_role', sa.String(length=50), nullable=False),
    sa.Column('is_attestation', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_by_user_id'], ['staff.id'], ),
    sa.ForeignKeyConstraint(['doctor_id'], ['referrers.id'], ),
    sa.ForeignKeyConstraint(['result_id'], ['results.id'], ),
    sa.ForeignKeyConstraint(['test_order_id'], ['test_orders.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('test_order_id', name='uq_doctor_approvals_test_order_id')
    )
    op.create_index('idx_doctor_approvals_tenant_doctor', 'doctor_approvals', ['tenant_id', 'doctor_id'], unique=False)
    op.create_index(op.f('ix_doctor_approvals_approved_by_user_id'), 'doctor_approvals', ['approved_by_user_id'], unique=False)
    op.create_index(op.f('ix_doctor_approvals_doctor_id'), 'doctor_approvals', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_doctor_approvals_tenant_id'), 'doctor_approvals', ['tenant_id'], unique=False)
    op.add_column('staff', sa.Column('doctor_profile_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_staff_doctor_profile', 'staff', 'referrers', ['doctor_profile_id'], ['id'])
    op.add_column('test_orders', sa.Column('assigned_doctor_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_test_orders_assigned_doctor_id'), 'test_orders', ['assigned_doctor_id'], unique=False)
    op.create_foreign_key('fk_test_orders_assigned_doctor', 'test_orders', 'referrers', ['assigned_doctor_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_test_orders_assigned_doctor', 'test_orders', type_='foreignkey')
    op.drop_index(op.f('ix_test_orders_assigned_doctor_id'), table_name='test_orders')
    op.drop_column('test_orders', 'assigned_doctor_id')
    op.drop_constraint('fk_staff_doctor_profile', 'staff', type_='foreignkey')
    op.drop_column('staff', 'doctor_profile_id')
    op.drop_index(op.f('ix_doctor_approvals_tenant_id'), table_name='doctor_approvals')
    op.drop_index(op.f('ix_doctor_approvals_doctor_id'), table_name='doctor_approvals')
    op.drop_index(op.f('ix_doctor_approvals_approved_by_user_id'), table_name='doctor_approvals')
    op.drop_index('idx_doctor_approvals_tenant_doctor', table_name='doctor_approvals')
    op.drop_table('doctor_approvals')


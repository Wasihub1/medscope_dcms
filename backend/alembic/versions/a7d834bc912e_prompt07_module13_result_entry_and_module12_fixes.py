"""prompt07_module13_result_entry_and_module12_fixes

Revision ID: a7d834bc912e
Revises: f16c024d3e4a
Create Date: 2026-11-07 22:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d834bc912e'
down_revision: Union[str, None] = 'f16c024d3e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create `test_components` table for Module 13 test parameter definitions
    op.create_table(
        'test_components',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('test_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('reference_range_text', sa.String(length=200), nullable=True),
        sa.Column('ref_min', sa.Float(), nullable=True),
        sa.Column('ref_max', sa.Float(), nullable=True),
        sa.Column('critical_min', sa.Float(), nullable=True),
        sa.Column('critical_max', sa.Float(), nullable=True),
        sa.Column('impossible_min', sa.Float(), nullable=True),
        sa.Column('impossible_max', sa.Float(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['test_id'], ['tests.id'], name='fk_test_components_test_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_test_components_tenant_id', 'test_components', ['tenant_id'], unique=False)
    op.create_index('ix_test_components_test_id', 'test_components', ['test_id'], unique=False)
    op.create_index('idx_test_comp_tenant_test', 'test_components', ['tenant_id', 'test_id', 'sort_order'], unique=False)

    # 2. Create `results` table for Module 13 result records
    op.create_table(
        'results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('test_order_id', sa.Integer(), nullable=False),
        sa.Column('result_type', sa.String(length=50), server_default='NUMERIC_TABLE', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ENTERED', nullable=False),
        sa.Column('findings', sa.Text(), nullable=True),
        sa.Column('impression', sa.Text(), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('structured_data', sa.JSON(), nullable=True),
        sa.Column('entered_by_id', sa.Integer(), nullable=False),
        sa.Column('entered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['entered_by_id'], ['staff.id'], name='fk_results_entered_by_id'),
        sa.ForeignKeyConstraint(['test_order_id'], ['test_orders.id'], name='fk_results_test_order_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('test_order_id', name='uq_results_test_order_id'),
    )
    op.create_index('ix_results_tenant_id', 'results', ['tenant_id'], unique=False)
    op.create_index('ix_results_test_order_id', 'results', ['test_order_id'], unique=False)
    op.create_index('idx_result_tenant_order', 'results', ['tenant_id', 'test_order_id'], unique=False)

    # 3. Create `result_items` table for individual result component rows & snapshot ranges
    op.create_table(
        'result_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('result_id', sa.Integer(), nullable=False),
        sa.Column('test_component_id', sa.Integer(), nullable=True),
        sa.Column('component_name', sa.String(length=200), nullable=False),
        sa.Column('component_code', sa.String(length=50), nullable=True),
        sa.Column('value', sa.String(length=200), nullable=False),
        sa.Column('numeric_value', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('reference_range', sa.String(length=200), nullable=True),
        sa.Column('ref_min', sa.Float(), nullable=True),
        sa.Column('ref_max', sa.Float(), nullable=True),
        sa.Column('critical_min', sa.Float(), nullable=True),
        sa.Column('critical_max', sa.Float(), nullable=True),
        sa.Column('impossible_min', sa.Float(), nullable=True),
        sa.Column('impossible_max', sa.Float(), nullable=True),
        sa.Column('flag', sa.String(length=50), nullable=True),
        sa.Column('comment', sa.String(length=300), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['result_id'], ['results.id'], name='fk_result_items_result_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_component_id'], ['test_components.id'], name='fk_result_items_test_component_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_result_items_tenant_id', 'result_items', ['tenant_id'], unique=False)
    op.create_index('ix_result_items_result_id', 'result_items', ['result_id'], unique=False)
    op.create_index('idx_result_item_tenant_result', 'result_items', ['tenant_id', 'result_id', 'sort_order'], unique=False)

    # 4. Add `outcome` column to `test_orders` for D15 Not Performed tracking
    op.add_column('test_orders', sa.Column('outcome', sa.String(length=50), nullable=True))

    # 5. Add D15 and Disbursement columns to `refund_requests`
    op.add_column('refund_requests', sa.Column('request_type', sa.String(length=50), server_default='PRE_SAMPLE_CANCELLATION', nullable=False))
    op.create_index('ix_refund_requests_request_type', 'refund_requests', ['request_type'], unique=False)
    op.add_column('refund_requests', sa.Column('disbursed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('refund_requests', sa.Column('disbursed_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_refund_requests_disbursed_by_id', 'refund_requests', 'staff', ['disbursed_by_id'], ['id'])
    op.add_column('refund_requests', sa.Column('disbursement_method', sa.String(length=50), nullable=True))
    op.add_column('refund_requests', sa.Column('disbursement_reference', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # 5. Drop refund disbursement columns
    op.drop_constraint('fk_refund_requests_disbursed_by_id', 'refund_requests', type_='foreignkey')
    op.drop_index('ix_refund_requests_request_type', table_name='refund_requests')
    op.drop_column('refund_requests', 'disbursement_reference')
    op.drop_column('refund_requests', 'disbursement_method')
    op.drop_column('refund_requests', 'disbursed_by_id')
    op.drop_column('refund_requests', 'disbursed_at')
    op.drop_column('refund_requests', 'request_type')

    # 4. Drop outcome from test_orders
    op.drop_column('test_orders', 'outcome')

    # 3. Drop result_items table
    op.drop_index('idx_result_item_tenant_result', table_name='result_items')
    op.drop_index('ix_result_items_result_id', table_name='result_items')
    op.drop_index('ix_result_items_tenant_id', table_name='result_items')
    op.drop_table('result_items')

    # 2. Drop results table
    op.drop_index('idx_result_tenant_order', table_name='results')
    op.drop_index('ix_results_test_order_id', table_name='results')
    op.drop_index('ix_results_tenant_id', table_name='results')
    op.drop_table('results')

    # 1. Drop test_components table
    op.drop_index('idx_test_comp_tenant_test', table_name='test_components')
    op.drop_index('ix_test_components_test_id', table_name='test_components')
    op.drop_index('ix_test_components_tenant_id', table_name='test_components')
    op.drop_table('test_components')


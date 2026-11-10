"""prompt06_module12_specimen_lifecycle

Revision ID: f16c024d3e4a
Revises: e05b9b1a2c3d
Create Date: 2026-11-07 19:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f16c024d3e4a'
down_revision: Union[str, None] = 'e05b9b1a2c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Specimen Lifecycle & Rejection Audit columns to `samples`
    op.add_column('samples', sa.Column('temp_sample_id', sa.String(length=50), nullable=True))
    op.create_index('ix_samples_temp_sample_id', 'samples', ['temp_sample_id'], unique=False)
    op.add_column('samples', sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('samples', sa.Column('rejected_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_samples_rejected_by_id_staff', 'samples', 'staff', ['rejected_by_id'], ['id'])
    op.add_column('samples', sa.Column('rejection_reason', sa.String(length=255), nullable=True))
    op.add_column('samples', sa.Column('rejection_notes', sa.String(length=500), nullable=True))

    # 2. Add Line Lock columns to `invoice_lines`
    op.add_column('invoice_lines', sa.Column('is_locked', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('invoice_lines', sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoice_lines', sa.Column('locked_reason', sa.String(length=255), nullable=True))

    # 3. Add Module 12 department and tracking columns to `test_orders`
    op.add_column('test_orders', sa.Column('patient_followup_required', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('test_orders', sa.Column('patient_contact_status', sa.String(length=50), nullable=True))
    op.add_column('test_orders', sa.Column('patient_contacted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('test_orders', sa.Column('patient_contact_notes', sa.String(length=500), nullable=True))
    op.add_column('test_orders', sa.Column('culture_stage', sa.String(length=50), nullable=True))
    op.add_column('test_orders', sa.Column('outsourced_status', sa.String(length=50), nullable=True))
    op.add_column('test_orders', sa.Column('outsourced_lab_name', sa.String(length=100), nullable=True))
    op.add_column('test_orders', sa.Column('outsourced_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('test_orders', sa.Column('outsourced_received_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('test_orders', sa.Column('outsourced_ref_no', sa.String(length=100), nullable=True))

    # 4. Create `test_order_events` table for append-only operational lifecycle history
    op.create_table(
        'test_order_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('test_order_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('stage', sa.String(length=50), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_name', sa.String(length=100), nullable=True),
        sa.Column('actor_role', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['staff.id'], name='fk_test_order_events_actor_id_staff'),
        sa.ForeignKeyConstraint(['test_order_id'], ['test_orders.id'], name='fk_test_order_events_test_order_id_test_orders'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_test_order_events_tenant_id', 'test_order_events', ['tenant_id'], unique=False)
    op.create_index('ix_test_order_events_test_order_id', 'test_order_events', ['test_order_id'], unique=False)
    op.create_index('ix_test_order_events_event_type', 'test_order_events', ['event_type'], unique=False)
    op.create_index('idx_order_events_tenant_order', 'test_order_events', ['tenant_id', 'test_order_id', 'created_at'], unique=False)

    # 5. Backfill line locks for tests where samples are already collected
    op.execute(
        sa.text("""
            UPDATE invoice_lines
            SET is_locked = TRUE,
                locked_at = s.collected_at,
                locked_reason = 'Specimen collected (' || s.sample_code || ')'
            FROM test_orders to_tbl
            JOIN samples s ON to_tbl.id = s.test_order_id
            WHERE invoice_lines.id = to_tbl.invoice_line_id
              AND s.status = 'COLLECTED';
        """)
    )


def downgrade() -> None:
    op.drop_table('test_order_events')
    op.drop_column('test_orders', 'outsourced_ref_no')
    op.drop_column('test_orders', 'outsourced_received_at')
    op.drop_column('test_orders', 'outsourced_sent_at')
    op.drop_column('test_orders', 'outsourced_lab_name')
    op.drop_column('test_orders', 'outsourced_status')
    op.drop_column('test_orders', 'culture_stage')
    op.drop_column('test_orders', 'patient_contact_notes')
    op.drop_column('test_orders', 'patient_contacted_at')
    op.drop_column('test_orders', 'patient_contact_status')
    op.drop_column('test_orders', 'patient_followup_required')
    op.drop_column('invoice_lines', 'locked_reason')
    op.drop_column('invoice_lines', 'locked_at')
    op.drop_column('invoice_lines', 'is_locked')
    op.drop_column('samples', 'rejection_notes')
    op.drop_column('samples', 'rejection_reason')
    op.drop_constraint('fk_samples_rejected_by_id_staff', 'samples', type_='foreignkey')
    op.drop_column('samples', 'rejected_by_id')
    op.drop_column('samples', 'rejected_at')
    op.drop_index('ix_samples_temp_sample_id', table_name='samples')
    op.drop_column('samples', 'temp_sample_id')


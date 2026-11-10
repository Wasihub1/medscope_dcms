"""add_refund_status_to_invoices

Revision ID: bdc0201a1170
Revises: c94589ffc4ee
Create Date: 2026-11-07 02:46:02.934309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdc0201a1170'
down_revision: Union[str, None] = 'c94589ffc4ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add refund_status column with default 'NO_REFUND'
    op.add_column(
        'invoices',
        sa.Column('refund_status', sa.String(length=50), server_default='NO_REFUND', nullable=False)
    )
    op.create_index('ix_invoices_refund_status', 'invoices', ['refund_status'], unique=False)

    # 2. Backfill existing fully refunded invoices (all lines cancelled/refunded)
    op.execute(
        sa.text("""
            UPDATE invoices 
            SET refund_status = 'FULLY_REFUNDED'
            WHERE id IN (
                SELECT DISTINCT rr.invoice_id 
                FROM refund_requests rr
                WHERE rr.status = 'APPROVED'
            )
            AND NOT EXISTS (
                SELECT 1 FROM invoice_lines il 
                WHERE il.invoice_id = invoices.id 
                AND il.status != 'CANCELLED'
            )
        """)
    )

    # 3. Backfill existing partially refunded invoices (at least one line cancelled, but active lines remain)
    op.execute(
        sa.text("""
            UPDATE invoices 
            SET refund_status = 'PARTIALLY_REFUNDED'
            WHERE id IN (
                SELECT DISTINCT rr.invoice_id 
                FROM refund_requests rr
                WHERE rr.status = 'APPROVED'
            )
            AND EXISTS (
                SELECT 1 FROM invoice_lines il 
                WHERE il.invoice_id = invoices.id 
                AND il.status != 'CANCELLED'
            )
        """)
    )


def downgrade() -> None:
    op.drop_index('ix_invoices_refund_status', table_name='invoices')
    op.drop_column('invoices', 'refund_status')

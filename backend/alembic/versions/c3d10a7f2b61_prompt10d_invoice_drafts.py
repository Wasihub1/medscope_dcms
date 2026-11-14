"""prompt10d_invoice_drafts

Prompt 10D Part 3 — Invoice Draft / Finalize workflow.

Additive only:
- invoices.visit_id becomes nullable (a DRAFT has no visit yet; the visit is created at Finalize).
- invoices.draft_payload (JSON, nullable): the saved draft form (lines, discounts, payment intent, demographics).
- invoices.finalized_at (timestamptz, nullable): when the invoice was finalized.

Existing rows are untouched (all are CONFIRMED and keep their visit_id).

Revision ID: c3d10a7f2b61
Revises: b9e41d82f05a
Create Date: 2026-11-13 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c3d10a7f2b61'
down_revision: Union[str, None] = 'b9e41d82f05a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('invoices', 'visit_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('invoices', sa.Column('draft_payload', sa.JSON(), nullable=True))
    op.add_column('invoices', sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('invoices', 'finalized_at')
    op.drop_column('invoices', 'draft_payload')
    # Restoring NOT NULL requires that no DRAFT rows without a visit remain.
    op.alter_column('invoices', 'visit_id', existing_type=sa.Integer(), nullable=False)

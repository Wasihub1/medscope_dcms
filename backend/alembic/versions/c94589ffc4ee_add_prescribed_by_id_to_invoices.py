"""add_prescribed_by_id_to_invoices

Revision ID: c94589ffc4ee
Revises: 5e7d6e556c9d
Create Date: 2026-11-07 00:04:05.145484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c94589ffc4ee'
down_revision: Union[str, None] = '5e7d6e556c9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('prescribed_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_invoices_prescribed_by_id_referrers', 'invoices', 'referrers', ['prescribed_by_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_invoices_prescribed_by_id_referrers', 'invoices', type_='foreignkey')
    op.drop_column('invoices', 'prescribed_by_id')


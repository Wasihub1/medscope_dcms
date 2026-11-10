"""prompt05_catalog_routing_worklist

Revision ID: e05b9b1a2c3d
Revises: bdc0201a1170
Create Date: 2026-11-07 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e05b9b1a2c3d'
down_revision: Union[str, None] = 'bdc0201a1170'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Test Catalog Readiness columns to `tests`
    op.add_column('tests', sa.Column('turnaround_hours', sa.Integer(), nullable=True))
    op.add_column('tests', sa.Column('performing_role', sa.String(length=50), server_default='LAB_TECH', nullable=False))
    op.add_column('tests', sa.Column('requires_doctor', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('tests', sa.Column('report_template', sa.String(length=50), server_default='NUMERIC_TABLE', nullable=False))
    op.add_column('tests', sa.Column('approval_rule', sa.String(length=50), server_default='TECHNICIAN_FINAL', nullable=False))
    op.add_column('tests', sa.Column('is_outsourced', sa.Boolean(), server_default=sa.false(), nullable=False))

    # 2. Add department column to `staff` for role & department based routing
    op.add_column('staff', sa.Column('department', sa.String(length=100), nullable=True))
    op.create_index('ix_staff_department', 'staff', ['department'], unique=False)

    # 3. Add default_sample_route to `tenants`
    op.add_column('tenants', sa.Column('default_sample_route', sa.String(length=20), server_default='QUICK', nullable=False))

    # 4. Add routing & turnaround tracking columns to `test_orders`
    op.add_column('test_orders', sa.Column('urgent', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('test_orders', sa.Column('department', sa.String(length=100), nullable=True))
    op.add_column('test_orders', sa.Column('performing_role', sa.String(length=50), server_default='LAB_TECH', nullable=False))
    op.add_column('test_orders', sa.Column('turnaround_hours', sa.Integer(), nullable=True))
    op.add_column('test_orders', sa.Column('sample_route', sa.String(length=20), server_default='QUICK', nullable=False))

    # 5. Backfill existing staff departments
    op.execute(
        sa.text("""
            UPDATE staff SET department = 'Hematology' WHERE username = 'tech_kamal' OR id = 3;
            UPDATE staff SET department = 'Biochemical Tests' WHERE username = 'tech_nasrin' OR id = 4;
        """)
    )

    # 6. Backfill existing tests configuration
    op.execute(
        sa.text("""
            UPDATE tests SET turnaround_hours = 4, performing_role = 'LAB_TECH', report_template = 'NUMERIC_TABLE', approval_rule = 'TECHNICIAN_FINAL'
            WHERE code IN ('CBC', 'HGB', 'BTCT', 'RBS', 'FBS', 'HBA1C', 'LIPID', 'CREAT', 'UREA', 'SGPT', 'SGOT', 'BILI', 'ELC');

            UPDATE tests SET turnaround_hours = 3, performing_role = 'LAB_TECH', report_template = 'NUMERIC_TABLE', approval_rule = 'TECHNICIAN_FINAL'
            WHERE code IN ('URINE', 'STOOL');

            UPDATE tests SET turnaround_hours = 6, performing_role = 'LAB_TECH', report_template = 'NUMERIC_TABLE', approval_rule = 'TECHNICIAN_FINAL'
            WHERE code IN ('TSH', 'FT4', 'HBSAG', 'HIV', 'WIDAL');

            UPDATE tests SET turnaround_hours = 2, requires_doctor = TRUE, performing_role = 'DOCTOR', report_template = 'NARRATIVE', approval_rule = 'DOCTOR_REQUIRED'
            WHERE code IN ('USG_W_A', 'USG_L_A', 'USG_PREG');

            UPDATE tests SET turnaround_hours = 48, performing_role = 'LAB_TECH', report_template = 'CULTURE_SENSITIVITY', approval_rule = 'BOTH_SIGNATURES'
            WHERE code = 'URINE_C_S';

            UPDATE tests SET turnaround_hours = 4, requires_doctor = TRUE, performing_role = 'DOCTOR', report_template = 'NARRATIVE', approval_rule = 'DOCTOR_REQUIRED'
            WHERE code = 'XRAY_CHEST';
        """)
    )

    # 7. Backfill existing test_orders from invoice_lines and tests
    op.execute(
        sa.text("""
            UPDATE test_orders
            SET urgent = il.urgent,
                department = il.department_snapshot,
                turnaround_hours = t.turnaround_hours,
                performing_role = t.performing_role
            FROM invoice_lines il
            JOIN tests t ON il.test_id = t.id
            WHERE test_orders.invoice_line_id = il.id;
        """)
    )

    # 8. Set Awaiting Doctor status for USG orders that are not completed
    op.execute(
        sa.text("""
            UPDATE test_orders
            SET status = 'AWAITING_DOCTOR'
            WHERE performing_role = 'DOCTOR' AND status NOT IN ('COMPLETED', 'CANCELLED');
        """)
    )


def downgrade() -> None:
    op.drop_column('test_orders', 'sample_route')
    op.drop_column('test_orders', 'turnaround_hours')
    op.drop_column('test_orders', 'performing_role')
    op.drop_column('test_orders', 'department')
    op.drop_column('test_orders', 'urgent')

    op.drop_column('tenants', 'default_sample_route')

    op.drop_index('ix_staff_department', table_name='staff')
    op.drop_column('staff', 'department')

    op.drop_column('tests', 'is_outsourced')
    op.drop_column('tests', 'approval_rule')
    op.drop_column('tests', 'report_template')
    op.drop_column('tests', 'requires_doctor')
    op.drop_column('tests', 'performing_role')
    op.drop_column('tests', 'turnaround_hours')


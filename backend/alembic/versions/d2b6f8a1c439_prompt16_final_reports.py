"""prompt16_final_reports: Module 14 Draft to Final report

The report_versions table already existed (seeded, used by delivery), so it is EXTENDED, not replaced:
result_id, approval_rule, doctor_approval_id, content_snapshot (JSON), signatures (JSON), all nullable
(seeded rows keep NULL). Autogenerate was reviewed by hand: the three unnamed foreign keys got names
(the generated downgrade would have failed); a database trigger was added by hand because autogenerate
cannot express it: it refuses any UPDATE that changes the stored content of a report version
(content, signatures, numbers, issuer, time). results.updated_by_id supports the edit-conflict check.
Also new: notification_log (placeholder rows only, nothing is sent) and a partial unique index so a
test order has at most one Final report.

Revision ID: d2b6f8a1c439
Revises: c9a4e7b2d815
Create Date: 2026-11-14 13:20:56.351973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b6f8a1c439'
down_revision: Union[str, None] = 'c9a4e7b2d815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('notification_log',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('report_version_id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['report_version_id'], ['report_versions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_log_report_version_id'), 'notification_log', ['report_version_id'], unique=False)
    op.create_index(op.f('ix_notification_log_tenant_id'), 'notification_log', ['tenant_id'], unique=False)
    op.add_column('report_versions', sa.Column('result_id', sa.Integer(), nullable=True))
    op.add_column('report_versions', sa.Column('approval_rule', sa.String(length=50), nullable=True))
    op.add_column('report_versions', sa.Column('doctor_approval_id', sa.Integer(), nullable=True))
    op.add_column('report_versions', sa.Column('content_snapshot', sa.JSON(), nullable=True))
    op.add_column('report_versions', sa.Column('signatures', sa.JSON(), nullable=True))
    op.create_index('uq_report_versions_final_per_order', 'report_versions', ['test_order_id'], unique=True, postgresql_where=sa.text("status = 'FINAL_AUTHORIZED'"))
    op.create_foreign_key('fk_report_versions_result', 'report_versions', 'results', ['result_id'], ['id'])
    op.create_foreign_key('fk_report_versions_doctor_approval', 'report_versions', 'doctor_approvals', ['doctor_approval_id'], ['id'])
    op.add_column('results', sa.Column('updated_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_results_updated_by', 'results', 'staff', ['updated_by_id'], ['id'])
    # Immutability of a report version's stored content, for every writer (not only the ORM).
    op.execute("""
    CREATE FUNCTION report_versions_immutable() RETURNS trigger AS $$
    BEGIN
      IF NEW.test_order_id IS DISTINCT FROM OLD.test_order_id
         OR NEW.report_no IS DISTINCT FROM OLD.report_no
         OR NEW.version IS DISTINCT FROM OLD.version
         OR NEW.findings_summary IS DISTINCT FROM OLD.findings_summary
         OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
         OR NEW.issued_by_id IS DISTINCT FROM OLD.issued_by_id
         OR NEW.result_id IS DISTINCT FROM OLD.result_id
         OR NEW.approval_rule IS DISTINCT FROM OLD.approval_rule
         OR NEW.doctor_approval_id IS DISTINCT FROM OLD.doctor_approval_id
         OR NEW.content_snapshot::text IS DISTINCT FROM OLD.content_snapshot::text
         OR NEW.signatures::text IS DISTINCT FROM OLD.signatures::text THEN
        RAISE EXCEPTION 'A report version is immutable: its stored content cannot be changed (report_versions.id=%)', OLD.id;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("CREATE TRIGGER trg_report_versions_immutable BEFORE UPDATE ON report_versions FOR EACH ROW EXECUTE FUNCTION report_versions_immutable()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_report_versions_immutable ON report_versions")
    op.execute("DROP FUNCTION IF EXISTS report_versions_immutable()")
    op.drop_constraint('fk_results_updated_by', 'results', type_='foreignkey')
    op.drop_column('results', 'updated_by_id')
    op.drop_constraint('fk_report_versions_doctor_approval', 'report_versions', type_='foreignkey')
    op.drop_constraint('fk_report_versions_result', 'report_versions', type_='foreignkey')
    op.drop_index('uq_report_versions_final_per_order', table_name='report_versions', postgresql_where=sa.text("status = 'FINAL_AUTHORIZED'"))
    op.drop_column('report_versions', 'signatures')
    op.drop_column('report_versions', 'content_snapshot')
    op.drop_column('report_versions', 'doctor_approval_id')
    op.drop_column('report_versions', 'approval_rule')
    op.drop_column('report_versions', 'result_id')
    op.drop_index(op.f('ix_notification_log_tenant_id'), table_name='notification_log')
    op.drop_index(op.f('ix_notification_log_report_version_id'), table_name='notification_log')
    op.drop_table('notification_log')

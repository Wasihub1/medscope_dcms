"""Prompt 11: soft delete columns (Category A: users, referrers/doctors, catalog tests).

Adds three NULLABLE columns to each of staff, referrers and tests, plus an index on deleted_at:
  deleted_at (timestamptz), deleted_by_id (FK staff.id), delete_reason (varchar 500).
NULL deleted_at = not deleted. No existing row is changed; downgrade drops only these columns.
The Audit Log viewer reuses audit_logs as is (no schema change for it).

Revision ID: a4d8c2e6f1b7
Revises: f3c9a1d7e5b2
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "a4d8c2e6f1b7"
down_revision = "f3c9a1d7e5b2"
branch_labels = None
depends_on = None

TABLES = ("staff", "referrers", "tests")


def upgrade() -> None:
    for t in TABLES:
        op.add_column(t, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(t, sa.Column("deleted_by_id", sa.Integer(), nullable=True))
        op.add_column(t, sa.Column("delete_reason", sa.String(length=500), nullable=True))
        op.create_foreign_key(f"fk_{t}_deleted_by_id_staff", t, "staff", ["deleted_by_id"], ["id"])
        op.create_index(op.f(f"ix_{t}_deleted_at"), t, ["deleted_at"], unique=False)


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_index(op.f(f"ix_{t}_deleted_at"), table_name=t)
        op.drop_constraint(f"fk_{t}_deleted_by_id_staff", t, type_="foreignkey")
        op.drop_column(t, "delete_reason")
        op.drop_column(t, "deleted_by_id")
        op.drop_column(t, "deleted_at")

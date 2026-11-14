"""Prompt 10E Part 7: room-based routing.

- tests.lab_section (nullable, indexed) backfilled from the mapping in
  backend/app/core/lab_sections.py (default_assignee -> department -> performing_role).
  Tests that map to no room stay NULL.
- test_orders.lab_section (nullable, indexed). Existing orders are re-routed by the one-off
  script backend/scripts/reroute_orders_to_rooms.py (dry run by default), not here.
- LAB_TECH rows without a room get one from their department when it maps unambiguously.
- CHECK (role <> 'LAB_TECH' OR lab_section IS NOT NULL) on staff, added only when every
  existing row satisfies it; otherwise the rule is enforced by the user service only and the
  migration prints which rows block it (no data is changed or deleted to force it).

Revision ID: f3c9a1d7e5b2
Revises: e8b2f4a6c1d3
Create Date: 2026-11-13
"""
import sys
from pathlib import Path

from alembic import op
import sqlalchemy as sa

# The test -> room mapping lives in one place (backend/app/core/lab_sections.py). Make the
# repository root importable even when Alembic loads this file without env.py (e.g. `heads`).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.app.core.lab_sections import section_for_test_fields, section_from_text  # noqa: E402


revision = "f3c9a1d7e5b2"
down_revision = "e8b2f4a6c1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tests", sa.Column("lab_section", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_tests_lab_section"), "tests", ["lab_section"], unique=False)
    op.add_column("test_orders", sa.Column("lab_section", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_test_orders_lab_section"), "test_orders", ["lab_section"], unique=False)

    bind = op.get_bind()

    # Backfill tests.lab_section from the single mapping
    rows = bind.execute(sa.text("SELECT id, department, default_assignee, performing_role FROM tests")).fetchall()
    per_section = {}
    for test_id, department, default_assignee, performing_role in rows:
        code = section_for_test_fields(department, default_assignee, performing_role)
        if code:
            bind.execute(sa.text("UPDATE tests SET lab_section = :c WHERE id = :i"), {"c": code, "i": test_id})
            per_section[code] = per_section.get(code, 0) + 1
    print(f"[prompt10e] tests.lab_section backfilled: {per_section} (unmapped: {len(rows) - sum(per_section.values())})")

    # LAB_TECH users without a room: take it from the department when it maps
    techs = bind.execute(sa.text(
        "SELECT id, department FROM staff WHERE role = 'LAB_TECH' AND lab_section IS NULL"
    )).fetchall()
    for staff_id, department in techs:
        code = section_from_text(department)
        if code:
            bind.execute(sa.text("UPDATE staff SET lab_section = :c WHERE id = :i"), {"c": code, "i": staff_id})

    remaining = bind.execute(sa.text(
        "SELECT id, username FROM staff WHERE role = 'LAB_TECH' AND lab_section IS NULL ORDER BY id"
    )).fetchall()
    if remaining:
        print(
            "[prompt10e] CHECK chk_staff_lab_tech_has_section NOT added: LAB_TECH rows without a room: "
            + ", ".join(f"{u} (#{i})" for i, u in remaining)
            + ". The rule is enforced by the user service; give these users a room, then re-check."
        )
    else:
        op.create_check_constraint(
            "chk_staff_lab_tech_has_section", "staff", "role <> 'LAB_TECH' OR lab_section IS NOT NULL"
        )


def downgrade() -> None:
    op.execute("ALTER TABLE staff DROP CONSTRAINT IF EXISTS chk_staff_lab_tech_has_section")
    op.drop_index(op.f("ix_test_orders_lab_section"), table_name="test_orders")
    op.drop_column("test_orders", "lab_section")
    op.drop_index(op.f("ix_tests_lab_section"), table_name="tests")
    op.drop_column("tests", "lab_section")

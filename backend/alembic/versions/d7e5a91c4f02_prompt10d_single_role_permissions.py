"""prompt10d_single_role_permissions

Prompt 10D Parts 4 and 5.

1. Data step — one login = one fixed role. Every staff member that holds more than one
   staff_roles row keeps the primary role; each extra role is moved (UPDATE, not DELETE) to a
   NEW staff account created for that role (username <role-prefix>_<suffix>, same tenant, same
   person details, same password hash copied in SQL so the existing dev password keeps working
   and is never read or printed). An ACCOUNT_SPLIT_SINGLE_ROLE audit row is written per split.
   Existing audit_logs rows are untouched.
2. Constraint uq_staff_roles_staff_id: at most one staff_roles row per staff member.
3. staff.lab_section (nullable): lab section/room code (see backend/app/core/lab_sections.py).
4. staff_permission_overrides: per-user grant/revoke on top of role defaults.

No data is deleted. Downgrade drops the new constraint/column/table but does not merge split
accounts back (that would need a manual decision).

Revision ID: d7e5a91c4f02
Revises: c3d10a7f2b61
Create Date: 2026-11-13 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd7e5a91c4f02'
down_revision: Union[str, None] = 'c3d10a7f2b61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE_PREFIX = {
    "OWNER": ("owner", "Owner"),
    "ADMIN": ("admin", "Admin"),
    "RECEPTIONIST": ("reception", "Receptionist"),
    "CASHIER": ("cashier", "Cashier"),
    "LAB_TECH": ("tech", "Lab Tech"),
}


def _sync_sequence(bind, table: str) -> None:
    """Seed scripts insert explicit ids, so serial sequences can lag behind MAX(id)."""
    bind.execute(sa.text(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))"
    ))


def _split_multi_role_accounts(bind) -> None:
    for table in ("staff", "staff_roles", "audit_logs"):
        _sync_sequence(bind, table)
    multi = bind.execute(sa.text(
        "SELECT staff_id FROM staff_roles GROUP BY staff_id HAVING COUNT(*) > 1 ORDER BY staff_id"
    )).scalars().all()
    for staff_id in multi:
        staff = bind.execute(sa.text(
            "SELECT id, tenant_id, username, display_name, role, department, phone, address, active, "
            "password_hash, password_changed_at FROM staff WHERE id = :id"
        ), {"id": staff_id}).mappings().one()
        roles = bind.execute(sa.text(
            "SELECT id, role, is_primary FROM staff_roles WHERE staff_id = :id ORDER BY is_primary DESC, id"
        ), {"id": staff_id}).mappings().all()
        primary = next((r for r in roles if r["is_primary"]), None) \
            or next((r for r in roles if r["role"] == staff["role"]), None) or roles[0]
        bind.execute(sa.text("UPDATE staff_roles SET is_primary = true WHERE id = :rid"), {"rid": primary["id"]})
        bind.execute(sa.text("UPDATE staff SET role = :role WHERE id = :id"), {"role": primary["role"], "id": staff_id})

        suffix = staff["username"].split("_", 1)[1] if "_" in staff["username"] else staff["username"]
        for extra in [r for r in roles if r["id"] != primary["id"]]:
            prefix, label = _ROLE_PREFIX.get(extra["role"], (extra["role"].lower(), extra["role"].title()))
            base = f"{prefix}_{suffix}"
            new_username, n = base, 2
            while bind.execute(sa.text("SELECT 1 FROM staff WHERE lower(username) = lower(:u)"), {"u": new_username}).first():
                new_username, n = f"{base}_{n}", n + 1
            new_id = bind.execute(sa.text(
                "INSERT INTO staff (tenant_id, username, display_name, role, department, email, phone, address, "
                "avatar_url, active, created_at, password_hash, failed_attempts, locked_at, last_login_at, password_changed_at) "
                "VALUES (:tenant_id, :username, :display_name, :role, :department, NULL, :phone, :address, NULL, :active, "
                "now(), :password_hash, 0, NULL, NULL, :password_changed_at) RETURNING id"
            ), {
                "tenant_id": staff["tenant_id"], "username": new_username,
                "display_name": f"{staff['display_name']} — {label}"[:150], "role": extra["role"],
                "department": staff["department"], "phone": staff["phone"], "address": staff["address"],
                "active": staff["active"], "password_hash": staff["password_hash"],
                "password_changed_at": staff["password_changed_at"],
            }).scalar_one()
            # Move (not delete) the extra role row to the new account
            bind.execute(sa.text("UPDATE staff_roles SET staff_id = :new_id, is_primary = true WHERE id = :rid"),
                         {"new_id": new_id, "rid": extra["id"]})
            bind.execute(sa.text(
                "INSERT INTO audit_logs (tenant_id, actor_id, acting_role, action, entity_type, entity_id, before_value, after_value, created_at) "
                "VALUES (:tenant_id, NULL, 'SYSTEM', 'ACCOUNT_SPLIT_SINGLE_ROLE', 'STAFF', :entity_id, :before, :after, now())"
            ), {
                "tenant_id": staff["tenant_id"], "entity_id": str(new_id),
                "before": f"{staff['username']} held role {extra['role']} in addition to {primary['role']}",
                "after": f"Role {extra['role']} moved to new single-role account {new_username} (Prompt 10D)",
            })


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Data: split multi-role accounts (no deletes)
    _split_multi_role_accounts(bind)
    # Keep staff.role in sync with the single staff_roles row
    bind.execute(sa.text(
        "UPDATE staff SET role = sr.role FROM staff_roles sr WHERE sr.staff_id = staff.id AND staff.role <> sr.role"
    ))

    # 2. One role per user
    op.create_unique_constraint('uq_staff_roles_staff_id', 'staff_roles', ['staff_id'])

    # 3. Lab section on staff
    op.add_column('staff', sa.Column('lab_section', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_staff_lab_section'), 'staff', ['lab_section'], unique=False)

    # 4. Per-user permission overrides
    op.create_table(
        'staff_permission_overrides',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('staff_id', sa.Integer(), nullable=False),
        sa.Column('permission_key', sa.String(length=100), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('changed_by_id', sa.Integer(), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by_id'], ['staff.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('staff_id', 'permission_key', name='uq_staff_permission_override'),
    )
    op.create_index(op.f('ix_staff_permission_overrides_tenant_id'), 'staff_permission_overrides', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_staff_permission_overrides_staff_id'), 'staff_permission_overrides', ['staff_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_staff_permission_overrides_staff_id'), table_name='staff_permission_overrides')
    op.drop_index(op.f('ix_staff_permission_overrides_tenant_id'), table_name='staff_permission_overrides')
    op.drop_table('staff_permission_overrides')
    op.drop_index(op.f('ix_staff_lab_section'), table_name='staff')
    op.drop_column('staff', 'lab_section')
    op.drop_constraint('uq_staff_roles_staff_id', 'staff_roles', type_='unique')

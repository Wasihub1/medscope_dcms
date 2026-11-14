"""
MedScope DCMS — User & Credentials Management CLI (Prompt 09)

Provides secure, auditable user administration commands:
- list-users: View all staff members, their assigned roles, and security status.
- set-password: Set/reset a password (read via hidden prompt or env var, never command arguments).
- create-user: Provision a new staff user with designated roles.
- assign-role: Add an operational role to an existing user.
- remove-role: Remove an operational role from an existing user.
- unlock: Clear account lockout and reset failed login attempts.
- lock: Manually lock a user account.
- init-staff-passwords: Set initial credentials for existing staff members.

Security note:
Passwords are NEVER passed as command-line arguments to prevent leakage into shell history and process lists.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select, func
from backend.app.core.database import SessionLocal
from backend.app.core.timezone import utc_now
from backend.app.models.user import Staff, StaffRole
from backend.app.services.auth_service import (
    hash_password,
    validate_password_strength,
    revoke_all_user_sessions,
    get_staff_roles,
)


def _get_password_input(prompt_msg: str, env_var: str | None = None) -> str:
    """Reads password from environment variable if provided, otherwise prompts via getpass."""
    if env_var:
        pwd = os.environ.get(env_var)
        if pwd:
            return pwd
    pwd1 = getpass.getpass(prompt_msg)
    pwd2 = getpass.getpass("Confirm password: ")
    if pwd1 != pwd2:
        print("Error: Passwords do not match.")
        sys.exit(1)
    return pwd1


def cmd_list_users(args):
    db = SessionLocal()
    try:
        staff_list = db.execute(select(Staff).order_by(Staff.id)).scalars().all()
        print("\n" + "=" * 90)
        print(f"{'ID':<4} {'Username':<18} {'Display Name':<28} {'Roles':<20} {'Status':<10} {'Locked'}")
        print("=" * 90)
        for s in staff_list:
            roles = get_staff_roles(db, s.id, s.role)
            role_str = ", ".join(roles)
            status_str = "Active" if s.active else "Inactive"
            locked_str = "LOCKED" if s.locked_at else "No"
            print(f"{s.id:<4} {s.username:<18} {s.display_name[:26]:<28} {role_str:<20} {status_str:<10} {locked_str}")
        print("=" * 90 + "\n")
    finally:
        db.close()


def cmd_set_password(args):
    db = SessionLocal()
    try:
        staff = db.execute(
            select(Staff).where(func.lower(Staff.username) == args.username.strip().lower())
        ).scalar_one_or_none()
        if not staff:
            print(f"Error: User '{args.username}' not found.")
            sys.exit(1)

        raw_pwd = _get_password_input(f"Enter new password for '{staff.username}': ", args.password_env)
        if not getattr(args, "force", False):
            try:
                validate_password_strength(raw_pwd, staff.username)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

        staff.password_hash = hash_password(raw_pwd)
        staff.password_changed_at = utc_now()
        staff.failed_attempts = 0
        staff.locked_at = None
        revoke_all_user_sessions(db, staff.id)
        db.commit()
        print(f"Success: Password for '{staff.username}' updated successfully.")
    finally:
        db.close()


def cmd_unlock(args):
    db = SessionLocal()
    try:
        staff = db.execute(
            select(Staff).where(func.lower(Staff.username) == args.username.strip().lower())
        ).scalar_one_or_none()
        if not staff:
            print(f"Error: User '{args.username}' not found.")
            sys.exit(1)

        staff.locked_at = None
        staff.failed_attempts = 0
        db.commit()
        print(f"Success: Account for '{staff.username}' unlocked successfully.")
    finally:
        db.close()


def cmd_lock(args):
    db = SessionLocal()
    try:
        staff = db.execute(
            select(Staff).where(func.lower(Staff.username) == args.username.strip().lower())
        ).scalar_one_or_none()
        if not staff:
            print(f"Error: User '{args.username}' not found.")
            sys.exit(1)

        staff.locked_at = utc_now()
        revoke_all_user_sessions(db, staff.id)
        db.commit()
        print(f"Success: Account for '{staff.username}' locked.")
    finally:
        db.close()


def cmd_assign_role(args):
    """Prompt 10D: one login = one fixed role. Sets (replaces) the user's single role.
    Prefer the Owner/Admin 'Create User' tab, which also enforces the last-admin rule."""
    from backend.app.core.permissions import ROLES
    db = SessionLocal()
    try:
        staff = db.execute(
            select(Staff).where(func.lower(Staff.username) == args.username.strip().lower())
        ).scalar_one_or_none()
        if not staff:
            print(f"Error: User '{args.username}' not found.")
            sys.exit(1)

        role = args.role.strip().upper()
        if role not in ROLES:
            print(f"Error: Unknown role '{role}'. Valid roles: {', '.join(ROLES)}.")
            sys.exit(1)
        rows = db.execute(select(StaffRole).where(StaffRole.staff_id == staff.id)).scalars().all()
        if rows and rows[0].role == role:
            print(f"User '{staff.username}' already has role '{role}'.")
            return
        if rows:
            rows[0].role = role
            rows[0].is_primary = True
        else:
            db.add(StaffRole(staff_id=staff.id, role=role, is_primary=True, created_at=utc_now()))
        lab_section = (getattr(args, "lab_section", None) or "").strip().upper() or None
        if role == "LAB_TECH":
            # Prompt 10E: a technician must belong to a lab room
            from backend.app.core.lab_sections import LAB_SECTIONS
            lab_section = lab_section or staff.lab_section
            if lab_section not in LAB_SECTIONS:
                print(f"Error: LAB_TECH needs --lab-section, one of: {', '.join(LAB_SECTIONS)}.")
                sys.exit(1)
        old_role = staff.role
        old_section = staff.lab_section
        old_counts = bool(staff.role == "LAB_TECH" and staff.active and staff.lab_section)
        staff.role = role
        staff.lab_section = lab_section if role == "LAB_TECH" else None
        db.flush()
        # Prompt 10F (A11): the same room routine as the Create User tab, in the same transaction:
        # the room the user left is checked for emptiness, the room they joined releases its orders.
        from backend.app.services.audit_service import log_audit_event
        from backend.app.services.routing_service import apply_technician_room_change
        log_audit_event(
            db=db, tenant_id=staff.tenant_id, action="USER_ROLE_CHANGED", entity_type="STAFF",
            entity_id=staff.id, acting_role="SYSTEM_CLI", actor_id=None,
            before_value=f"{old_role} (lab_section={old_section})",
            after_value=f"{role} (lab_section={staff.lab_section}) via manage_users.py",
        )
        demoted, released = apply_technician_room_change(
            db, staff.tenant_id, old_section, old_counts, staff.lab_section,
            bool(staff.role == "LAB_TECH" and staff.active and staff.lab_section),
            None, "SYSTEM_CLI", f"{staff.username}, role set by CLI",
        )
        db.commit()
        print(f"Success: '{staff.username}' now has the single role '{role}'.")
        if demoted or released:
            print(f"Room routing: {demoted} order(s) set UNASSIGNED, {released} order(s) released.")
    finally:
        db.close()


def cmd_remove_role(args):
    """Prompt 10D: every user holds exactly one role, so a role cannot be removed.
    Use 'assign-role' to change it, or deactivate the user in the Create User tab."""
    print("Error: Each user has exactly one role (Prompt 10D). Use 'assign-role' to change it.")
    sys.exit(1)


def cmd_create_user(args):
    db = SessionLocal()
    try:
        clean_user = args.username.strip()
        existing = db.execute(
            select(Staff).where(func.lower(Staff.username) == clean_user.lower())
        ).scalar_one_or_none()
        if existing:
            print(f"Error: User '{clean_user}' already exists.")
            sys.exit(1)

        raw_pwd = _get_password_input(f"Enter password for new user '{clean_user}': ", args.password_env)
        if not getattr(args, "force", False):
            try:
                validate_password_strength(raw_pwd, clean_user)
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)

        roles = [r.strip().upper() for r in args.roles.split(",") if r.strip()]
        if not roles:
            roles = ["RECEPTIONIST"]
        if len(roles) != 1:
            print("Error: One login = one fixed role (Prompt 10D). Give exactly one role in --roles.")
            sys.exit(1)
        from backend.app.core.permissions import ROLES
        from backend.app.core.lab_sections import LAB_SECTIONS
        if roles[0] not in ROLES:
            print(f"Error: Unknown role '{roles[0]}'. Valid roles: {', '.join(ROLES)}.")
            sys.exit(1)
        lab_section = (getattr(args, "lab_section", None) or "").strip().upper() or None
        if roles[0] == "LAB_TECH" and lab_section not in LAB_SECTIONS:
            print(f"Error: LAB_TECH needs --lab-section, one of: {', '.join(LAB_SECTIONS)} (Prompt 10E).")
            sys.exit(1)

        staff = Staff(
            tenant_id=args.tenant_id,
            username=clean_user,
            display_name=args.display_name.strip(),
            role=roles[0],
            department=args.department,
            lab_section=lab_section if roles[0] == "LAB_TECH" else None,
            email=args.email,
            phone=args.phone,
            active=True,
            password_hash=hash_password(raw_pwd),
            password_changed_at=utc_now(),
        )
        db.add(staff)
        db.flush()

        for idx, r in enumerate(roles):
            db.add(StaffRole(
                staff_id=staff.id,
                role=r,
                is_primary=(idx == 0),
                created_at=utc_now(),
            ))

        db.commit()
        print(f"Success: User '{staff.username}' created with ID {staff.id} and roles: {', '.join(roles)}.")
    finally:
        db.close()


def cmd_init_staff_passwords(args):
    """
    Sets initial credentials for the existing diagnostic staff:
    reception_fatima, admin_tariq, tech_kamal, tech_nasrin.
    """
    db = SessionLocal()
    try:
        staff_usernames = ["reception_fatima", "cashier_fatima", "admin_tariq", "owner_tariq", "tech_kamal", "tech_nasrin", "tech_micro", "tech_usg"]
        for uname in staff_usernames:
            staff = db.execute(
                select(Staff).where(func.lower(Staff.username) == uname)
            ).scalar_one_or_none()
            if not staff:
                print(f"Notice: Staff '{uname}' not found in database. Skipping.")
                continue

            env_name = f"MEDSCOPE_INIT_PASSWORD_{uname.upper()}"
            pwd = os.environ.get(env_name)
            if not pwd:
                pwd = _get_password_input(f"Enter password for '{staff.username}' ({staff.display_name}): ")

            if not getattr(args, "force", False):
                validate_password_strength(pwd, staff.username)
            staff.password_hash = hash_password(pwd)
            staff.password_changed_at = utc_now()
            staff.failed_attempts = 0
            staff.locked_at = None
            db.flush()
            print(f"Success: Set password for '{staff.username}'.")
        db.commit()
        print("\nAll existing staff accounts initialized successfully.")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="MedScope DCMS User & Credentials Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-users
    subparsers.add_parser("list-users", help="List all staff members and their roles")

    # set-password
    p_set = subparsers.add_parser("set-password", help="Set/reset a staff password")
    p_set.add_argument("--username", required=True, help="Staff username")
    p_set.add_argument("--password-env", help="Environment variable containing password")
    p_set.add_argument("--force", action="store_true", help="Bypass password strength policy (e.g. dev/test)")
    p_set.set_defaults(func=cmd_set_password)

    # unlock
    p_unlock = subparsers.add_parser("unlock", help="Unlock a locked user account")
    p_unlock.add_argument("--username", required=True, help="Staff username")
    p_unlock.set_defaults(func=cmd_unlock)

    # lock
    p_lock = subparsers.add_parser("lock", help="Lock a user account")
    p_lock.add_argument("--username", required=True, help="Staff username")
    p_lock.set_defaults(func=cmd_lock)

    # assign-role
    p_ar = subparsers.add_parser("assign-role", help="Set the user's single role (one login = one role)")
    p_ar.add_argument("--username", required=True, help="Staff username")
    p_ar.add_argument("--role", required=True, help="Role name (OWNER, ADMIN, RECEPTIONIST, CASHIER, LAB_TECH, DOCTOR)")
    p_ar.add_argument("--lab-section", dest="lab_section", help="Lab room for LAB_TECH (HEMATOLOGY, BIOCHEMISTRY, MICROBIOLOGY, ULTRASONOGRAPHY)")
    p_ar.add_argument("--primary", action="store_true", help="Ignored (kept for compatibility; every user has one role)")
    p_ar.set_defaults(func=cmd_assign_role)

    # remove-role
    p_rr = subparsers.add_parser("remove-role", help="Disabled: every user has exactly one role")
    p_rr.add_argument("--username", required=True, help="Staff username")
    p_rr.add_argument("--role", required=True, help="Role name to remove")
    p_rr.set_defaults(func=cmd_remove_role)

    # create-user
    p_cu = subparsers.add_parser("create-user", help="Create a new staff user")
    p_cu.add_argument("--username", required=True, help="Unique username")
    p_cu.add_argument("--display-name", required=True, help="Full display name")
    p_cu.add_argument("--roles", default="RECEPTIONIST", help="Exactly one role: OWNER, ADMIN, RECEPTIONIST, CASHIER, LAB_TECH or DOCTOR")
    p_cu.add_argument("--lab-section", dest="lab_section", help="Lab room, required for LAB_TECH (HEMATOLOGY, BIOCHEMISTRY, MICROBIOLOGY, ULTRASONOGRAPHY)")
    p_cu.add_argument("--tenant-id", default="center-seba-01", help="Tenant ID")
    p_cu.add_argument("--department", help="Department (e.g. Front Desk, Hematology)")
    p_cu.add_argument("--email", help="Email address")
    p_cu.add_argument("--phone", help="Phone number")
    p_cu.add_argument("--password-env", help="Environment variable containing password")
    p_cu.add_argument("--force", action="store_true", help="Bypass password strength policy (e.g. dev/test)")
    p_cu.set_defaults(func=cmd_create_user)

    # init-staff-passwords
    p_init = subparsers.add_parser("init-staff-passwords", help="Initialize credentials for existing staff")
    p_init.add_argument("--force", action="store_true", help="Bypass password strength policy (e.g. dev/test)")
    p_init.set_defaults(func=cmd_init_staff_passwords)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    elif args.command == "list-users":
        cmd_list_users(args)


if __name__ == "__main__":
    main()

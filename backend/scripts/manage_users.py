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
    db = SessionLocal()
    try:
        staff = db.execute(
            select(Staff).where(func.lower(Staff.username) == args.username.strip().lower())
        ).scalar_one_or_none()
        if not staff:
            print(f"Error: User '{args.username}' not found.")
            sys.exit(1)

        role = args.role.strip().upper()
        existing = db.execute(
            select(StaffRole).where(StaffRole.staff_id == staff.id, StaffRole.role == role)
        ).scalar_one_or_none()
        if existing:
            print(f"User '{staff.username}' already holds role '{role}'.")
            return

        new_role = StaffRole(
            staff_id=staff.id,
            role=role,
            is_primary=bool(args.primary),
            created_at=utc_now(),
        )
        db.add(new_role)
        db.commit()
        print(f"Success: Assigned role '{role}' to '{staff.username}'.")
    finally:
        db.close()


def cmd_remove_role(args):
    db = SessionLocal()
    try:
        staff = db.execute(
            select(Staff).where(func.lower(Staff.username) == args.username.strip().lower())
        ).scalar_one_or_none()
        if not staff:
            print(f"Error: User '{args.username}' not found.")
            sys.exit(1)

        role = args.role.strip().upper()
        existing = db.execute(
            select(StaffRole).where(StaffRole.staff_id == staff.id, StaffRole.role == role)
        ).scalar_one_or_none()
        if not existing:
            print(f"User '{staff.username}' does not hold role '{role}'.")
            return

        roles_count = db.execute(
            select(func.count(StaffRole.id)).where(StaffRole.staff_id == staff.id)
        ).scalar() or 0
        if roles_count <= 1:
            print(f"Error: Cannot remove role. User must hold at least one role.")
            sys.exit(1)

        db.delete(existing)
        db.commit()
        print(f"Success: Removed role '{role}' from '{staff.username}'.")
    finally:
        db.close()


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

        staff = Staff(
            tenant_id=args.tenant_id,
            username=clean_user,
            display_name=args.display_name.strip(),
            role=roles[0],
            department=args.department,
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
        staff_usernames = ["reception_fatima", "admin_tariq", "tech_kamal", "tech_nasrin"]
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
    p_ar = subparsers.add_parser("assign-role", help="Assign an additional role to a user")
    p_ar.add_argument("--username", required=True, help="Staff username")
    p_ar.add_argument("--role", required=True, help="Role name (e.g. ADMIN, RECEPTIONIST, LAB_TECH, OWNER, CASHIER)")
    p_ar.add_argument("--primary", action="store_true", help="Set as primary role")
    p_ar.set_defaults(func=cmd_assign_role)

    # remove-role
    p_rr = subparsers.add_parser("remove-role", help="Remove a role from a user")
    p_rr.add_argument("--username", required=True, help="Staff username")
    p_rr.add_argument("--role", required=True, help="Role name to remove")
    p_rr.set_defaults(func=cmd_remove_role)

    # create-user
    p_cu = subparsers.add_parser("create-user", help="Create a new staff user")
    p_cu.add_argument("--username", required=True, help="Unique username")
    p_cu.add_argument("--display-name", required=True, help="Full display name")
    p_cu.add_argument("--roles", default="RECEPTIONIST", help="Comma-separated roles")
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

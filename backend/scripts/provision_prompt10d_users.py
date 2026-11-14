"""
Prompt 10D Part 5 — assign one default LAB_TECH user per lab section/room (idempotent).

    python backend/scripts/provision_prompt10d_users.py            # dry run (prints the plan)
    python backend/scripts/provision_prompt10d_users.py --apply    # writes the changes

- tech_kamal  -> HEMATOLOGY      (Room 101)
- tech_nasrin -> BIOCHEMISTRY    (Room 102)
- tech_micro  -> MICROBIOLOGY    (Room 105)  (created if missing)
- tech_usg    -> ULTRASONOGRAPHY (Room 204)  (created if missing)

New users reuse the existing development password mechanism: their password hash is copied
from the reference account (tech_kamal), so they sign in with the same dev password. The
password is never read, printed or written to any file.

Routing is NOT changed (Prompt 10D Part 6): new users get no `department`, because the
existing routing code matches LAB_TECH users by department. See the Prompt 10D report for
the recommended routing fix.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from backend.app.core.database import SessionLocal  # noqa: E402
from backend.app.core.lab_sections import LAB_SECTIONS  # noqa: E402
from backend.app.core.timezone import utc_now  # noqa: E402
from backend.app.models.user import Staff, StaffRole  # noqa: E402
from backend.app.services.audit_service import log_audit_event  # noqa: E402

REFERENCE_USERNAME = "tech_kamal"
PLAN = [
    ("tech_kamal", "HEMATOLOGY", None),
    ("tech_nasrin", "BIOCHEMISTRY", None),
    ("tech_micro", "MICROBIOLOGY", "Microbiology Technician (Room 105)"),
    ("tech_usg", "ULTRASONOGRAPHY", "Ultrasonography Technician (Room 204)"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write changes (default is a dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        ref = db.execute(select(Staff).where(func.lower(Staff.username) == REFERENCE_USERNAME)).scalar_one_or_none()
        if not ref or not ref.password_hash:
            print(f"Reference account '{REFERENCE_USERNAME}' missing or has no password; nothing done.")
            return 1
        for username, section, display_name in PLAN:
            assert section in LAB_SECTIONS
            st = db.execute(select(Staff).where(func.lower(Staff.username) == username)).scalar_one_or_none()
            if st:
                if st.role != "LAB_TECH":
                    print(f"SKIP {username}: role is {st.role}, not LAB_TECH")
                    continue
                if st.lab_section == section:
                    print(f"OK   {username}: already {section}")
                    continue
                print(f"SET  {username}: lab_section {st.lab_section} -> {section}")
                if args.apply:
                    before = st.lab_section
                    st.lab_section = section
                    log_audit_event(db=db, tenant_id=st.tenant_id, action="USER_UPDATED", entity_type="STAFF",
                                    entity_id=st.id, acting_role="SYSTEM", actor_id=None,
                                    before_value=f"lab_section={before}", after_value=f"lab_section={section} (Prompt 10D)")
                continue
            print(f"NEW  {username}: LAB_TECH, {section} ({LAB_SECTIONS[section]['room']})")
            if args.apply:
                st = Staff(
                    tenant_id=ref.tenant_id,
                    username=username,
                    display_name=display_name,
                    role="LAB_TECH",
                    department=None,
                    lab_section=section,
                    active=True,
                    password_hash=ref.password_hash,  # existing dev password mechanism; never printed
                    password_changed_at=utc_now(),
                    failed_attempts=0,
                )
                db.add(st)
                db.flush()
                db.add(StaffRole(staff_id=st.id, role="LAB_TECH", is_primary=True, created_at=utc_now()))
                log_audit_event(db=db, tenant_id=st.tenant_id, action="USER_CREATED", entity_type="STAFF",
                                entity_id=st.id, acting_role="SYSTEM", actor_id=None,
                                after_value=f"username={username}, role=LAB_TECH, lab_section={section} (Prompt 10D default section user)")
        if args.apply:
            db.commit()
            print("Applied.")
        else:
            db.rollback()
            print("Dry run only. Re-run with --apply to write.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

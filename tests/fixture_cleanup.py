"""Prompt 12: removes the disposable Staff rows that tests create (random-suffix usernames).

ONLY ever runs against `medscope_test` (the database name is asserted first; the conftest hard guard
stays in place). Hard delete, by design: these are throwaway fixtures with no business meaning.

How rows that still point at a fixture user are handled (so no foreign key breaks and the suite keeps
working): cascade tables (sessions, roles, overrides) are deleted; every other column that references
`staff` is set to NULL when nullable, otherwise re-pointed at the seeded `owner_tariq`.
"""
from contextlib import contextmanager
from typing import Dict

from sqlalchemy import text
from sqlalchemy.engine import Connection

SEED_USERNAMES = (
    "reception_fatima", "cashier_fatima", "admin_tariq", "owner_tariq", "tech_kamal", "tech_nasrin",
    "tech_micro", "tech_usg", "doctor_rahim", "lockout_victim_user", "pw_change_user",
)
# Auto-generated names end in an underscore plus 6-8 hex characters (uuid4().hex[:n]).
FIXTURE_USERNAME_REGEX = "_[0-9a-f]{6,8}$"

_FIXTURE_WHERE = "username ~ :rx AND username <> ALL(:seed)"


@contextmanager
def audit_logs_writable_in_test_db(conn: Connection):
    """Prompt 19B: audit_logs is append-only in the application and in the database (trigger). These helpers hard-delete
    throwaway fixture rows in medscope_test only, so they switch the trigger off for the duration of the purge, inside the
    caller's transaction (the DB name is asserted first; the trigger is switched back on before returning). The product
    has no such path: nothing under backend/ can do this (tests/test_prompt19b_audit.py scans for it)."""
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test", "refusing: not medscope_test"
    conn.execute(text("ALTER TABLE audit_logs DISABLE TRIGGER USER"))
    try:
        yield
    finally:
        conn.execute(text("ALTER TABLE audit_logs ENABLE TRIGGER USER"))


def _params() -> Dict[str, object]:
    return {"rx": FIXTURE_USERNAME_REGEX, "seed": list(SEED_USERNAMES)}


def count_fixture_staff(conn: Connection) -> int:
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test"
    return conn.execute(text(f"SELECT count(*) FROM staff WHERE {_FIXTURE_WHERE}"), _params()).scalar_one()


def purge_fixture_staff(conn: Connection) -> int:
    """Hard-delete fixture Staff rows in medscope_test. Returns how many were deleted. Caller commits."""
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test", "refusing: not medscope_test"
    p = _params()
    ids = [r[0] for r in conn.execute(text(f"SELECT id FROM staff WHERE {_FIXTURE_WHERE}"), p)]
    if not ids:
        return 0
    owner_id = conn.execute(text("SELECT id FROM staff WHERE username = 'owner_tariq'")).scalar()
    assert owner_id is not None, "seed owner_tariq missing"
    fks = conn.execute(text(
        "SELECT con.conrelid::regclass::text, a.attname, con.confdeltype, a.attnotnull "
        "FROM pg_constraint con JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey) "
        "WHERE con.confrelid = 'staff'::regclass AND con.contype = 'f'"
    )).all()
    with audit_logs_writable_in_test_db(conn):
        for table, col, deltype, notnull in fks:
            if deltype == "c":  # ON DELETE CASCADE (sessions, roles, overrides)
                conn.execute(text(f'DELETE FROM "{table}" WHERE "{col}" = ANY(:ids)'), {"ids": ids})
            elif notnull:
                conn.execute(text(f'UPDATE "{table}" SET "{col}" = :o WHERE "{col}" = ANY(:ids)'), {"o": owner_id, "ids": ids})
            else:
                conn.execute(text(f'UPDATE "{table}" SET "{col}" = NULL WHERE "{col}" = ANY(:ids)'), {"ids": ids})
        # Audit rows ABOUT a purged user (entity STAFF/USER) go too: staff ids can otherwise be matched by a
        # later test against stale audit rows that carry the same id as text.
        conn.execute(
            text("DELETE FROM audit_logs WHERE entity_type IN ('STAFF', 'USER') AND entity_id = ANY(:sids)"),
            {"sids": [str(i) for i in ids]},
        )
        conn.execute(text("DELETE FROM staff WHERE id = ANY(:ids)"), {"ids": ids})
    return len(ids)


def purge_orphan_staff_audit_rows(conn: Connection) -> int:
    """One-time helper: audit rows about staff ids that no longer exist (left by earlier purges)."""
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test", "refusing: not medscope_test"
    with audit_logs_writable_in_test_db(conn):
        return conn.execute(text(
            "DELETE FROM audit_logs WHERE entity_type IN ('STAFF', 'USER') AND entity_id ~ '^[0-9]+$' "
            "AND entity_id::int NOT IN (SELECT id FROM staff)"
        )).rowcount


# ---------------------------------------------------------------------------
# Prompt 13A: the same teardown mechanism for the throwaway Referrer rows tests create.
# Seed referrers (ids 1-10, bilingual names) never match these patterns.
# ---------------------------------------------------------------------------
FIXTURE_REFERRER_NAME_REGEX = (
    r"^((Partner Agent|Dr\. Prescriber|Dr\. E2E Test) [0-9]+|(Dr Probe|Probe Clinic|Dr Audit) [0-9a-f]{6})$"
)


def count_fixture_referrers(conn: Connection) -> int:
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test"
    return conn.execute(text("SELECT count(*) FROM referrers WHERE name ~ :rx"), {"rx": FIXTURE_REFERRER_NAME_REGEX}).scalar_one()


def purge_fixture_referrers(conn: Connection) -> int:
    """Hard-delete fixture Referrer rows in medscope_test. Returns how many were deleted. Caller commits.
    Columns that reference `referrers` (invoices.referrer_id / prescribed_by_id) are set to NULL when
    nullable; audit rows about a purged referrer go with it."""
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test", "refusing: not medscope_test"
    ids = [r[0] for r in conn.execute(text("SELECT id FROM referrers WHERE name ~ :rx"), {"rx": FIXTURE_REFERRER_NAME_REGEX})]
    if not ids:
        return 0
    # Prompt 16: Final reports created from a throwaway doctor's approval (and their placeholder
    # notification rows) go first, because report_versions points at doctor_approvals.
    conn.execute(text(
        "DELETE FROM notification_log WHERE report_version_id IN (SELECT id FROM report_versions WHERE doctor_approval_id IN "
        "(SELECT id FROM doctor_approvals WHERE doctor_id = ANY(:ids)))"), {"ids": ids})
    conn.execute(text(
        "DELETE FROM report_versions WHERE doctor_approval_id IN (SELECT id FROM doctor_approvals WHERE doctor_id = ANY(:ids))"), {"ids": ids})
    fks = conn.execute(text(
        "SELECT con.conrelid::regclass::text, a.attname, con.confdeltype, a.attnotnull "
        "FROM pg_constraint con JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey) "
        "WHERE con.confrelid = 'referrers'::regclass AND con.contype = 'f'"
    )).all()
    for table, col, deltype, notnull in fks:
        if deltype == "c" or notnull:
            conn.execute(text(f'DELETE FROM "{table}" WHERE "{col}" = ANY(:ids)'), {"ids": ids})
        else:
            conn.execute(text(f'UPDATE "{table}" SET "{col}" = NULL WHERE "{col}" = ANY(:ids)'), {"ids": ids})
    with audit_logs_writable_in_test_db(conn):
        conn.execute(
            text("DELETE FROM audit_logs WHERE entity_type = 'REFERRER' AND entity_id = ANY(:sids)"),
            {"sids": [str(i) for i in ids]},
        )
    conn.execute(text("DELETE FROM referrers WHERE id = ANY(:ids)"), {"ids": ids})
    return len(ids)

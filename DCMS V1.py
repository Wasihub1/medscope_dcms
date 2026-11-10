from contextlib import contextmanager
import csv
from datetime import datetime
from html import escape
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components
from accounting import (
    account_id,
    accounting_screen,
    cash_account_key,
    ensure_accounting_schema,
    post_journal_entry,
)


APP_NAME = "MedScope"
LEGACY_DB_PATH = Path(__file__).with_name("seba_diagnostic.db")
DATA_DIR = Path(__file__).with_name("medscope_data")
TENANT_DATA_DIR = DATA_DIR / "tenants"
PLATFORM_DB_PATH = DATA_DIR / "platform.db"
ROLES = ("Owner", "Admin", "Receptionist", "Cashier", "Lab Tech")
PAYMENT_METHODS = ("Cash", "Card", "bKash", "Nagad", "Rocket", "Upay", "Bank transfer")
REFERENCE_REQUIRED_METHODS = ("bKash", "Nagad", "Rocket", "Upay", "Bank transfer")
COMMISSION_TYPES = ("Percentage", "Fixed amount")

st.set_page_config(page_title=APP_NAME, page_icon="✚", layout="wide")

keyboard_dropdown_component = components.declare_component(
    "seba_keyboard_dropdown",
    path=str(Path(__file__).with_name("keyboard_dropdown")),
)


def dropdown(label, options, multi=False, selected_option=None, key=None, allow_empty=False):
    options = list(options)
    if not options:
        raise ValueError(f"{label} dropdown requires at least one option.")
    page = st.session_state.get("navigation_page", "app")
    key = key or f"dropdown_{page}_{label}"
    if allow_empty:
        empty_selection_marker = f"{key}_empty_default_applied"
        if not st.session_state.get(empty_selection_marker):
            st.session_state.pop(key, None)
            st.session_state[empty_selection_marker] = True
    selected = st.session_state.get(key)
    if multi:
        if not isinstance(selected, list):
            selected = []
        selected = [option for option in selected if option in options]
    else:
        if selected_option in options:
            selected = selected_option
            st.session_state[key] = selected
        elif allow_empty:
            selected = selected if selected in options else None
        elif selected not in options:
            selected = options[0]
            st.session_state[key] = selected
    return keyboard_dropdown_component(
        label=label,
        options=options,
        selected=selected,
        multi=multi,
        key=key,
        default=selected,
    )


def remove_invoice_test(label):
    selection_key = "new_invoice_tests"
    selected_tests = st.session_state.get(selection_key, [])
    if not isinstance(selected_tests, list):
        raise TypeError("The selected invoice tests must be stored as a list.")
    if st.session_state.get("dropdown_new_invoice_tests"):
        selected_tests = st.session_state["dropdown_new_invoice_tests"]
    st.session_state[selection_key] = [
        selected for selected in selected_tests if selected != label
    ]


def set_invoice_line_discount_type(test_id, discount_type):
    st.session_state[f"new_invoice_line_discount_{test_id}_type"] = discount_type
    st.session_state[f"new_invoice_line_discount_{test_id}_enabled"] = True
    test_discounts = st.session_state.setdefault("new_invoice_test_discounts", {})
    test_discounts[str(test_id)] = {
        **test_discounts.get(str(test_id), {}),
        "enabled": True,
        "type": discount_type,
    }
    if discount_type == "Percentage":
        st.session_state[f"new_invoice_line_discount_{test_id}_percent_value"] = min(
            50.0,
            float(st.session_state.get(f"new_invoice_line_discount_{test_id}_percent_value", 50.0)),
        )


@contextmanager
def database(db_path=None):
    selected_path = db_path or st.session_state.get("tenant_db_path")
    if selected_path is None:
        raise RuntimeError("A tenant database context is required for this operation.")
    db_path = Path(selected_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if journal_mode.lower() != "wal":
            connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def platform_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(PLATFORM_DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def tenant_database_path(tenant_id):
    try:
        parsed_id = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("The tenant identifier is invalid.") from error
    return TENANT_DATA_DIR / f"{parsed_id.hex}.db"


def initialize_platform():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TENANT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    tenant_to_initialize = None
    with platform_database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                created_by INTEGER
            );
            CREATE TABLE IF NOT EXISTS platform_users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                totp_secret TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0,
                last_totp_counter INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS platform_audit (
                id INTEGER PRIMARY KEY,
                platform_user_id INTEGER REFERENCES platform_users(id),
                action TEXT NOT NULL,
                tenant_id TEXT REFERENCES tenants(id),
                details TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """
        )
        tenant_count = connection.execute(
            "SELECT COUNT(*) FROM tenants"
        ).fetchone()[0]
        if tenant_count == 0:
            tenant_id = str(uuid.uuid4())
            tenant_path = tenant_database_path(tenant_id)
            if LEGACY_DB_PATH.is_file():
                source = sqlite3.connect(LEGACY_DB_PATH, timeout=15)
                target = sqlite3.connect(tenant_path, timeout=15)
                try:
                    source.backup(target)
                finally:
                    target.close()
                    source.close()
            else:
                tenant_to_initialize = tenant_path
            connection.execute(
                """INSERT INTO tenants(id, slug, name, created_at)
                   VALUES (?, 'seba-diagnostic', 'Seba Diagnostic', ?)""",
                (tenant_id, now()),
            )
    if tenant_to_initialize is not None:
        initialize_database(tenant_to_initialize, allow_create=True)


def platform_tenants(active_only=False):
    query = "SELECT id, slug, name, active, created_at FROM tenants"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY name"
    with platform_database() as connection:
        return [dict(row) for row in connection.execute(query).fetchall()]


def tenant_staff_matches(username, active_tenants_only=True):
    matches = []
    tenants = platform_tenants(active_only=active_tenants_only)
    for tenant in tenants:
        tenant_path = tenant_database_path(tenant["id"])
        if not tenant_path.is_file():
            raise RuntimeError(
                "A registered diagnostic center database is unavailable. "
                "Contact MedScope Dev before signing in."
            )
        connection = sqlite3.connect(
            f"{tenant_path.as_uri()}?mode=ro",
            timeout=15,
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(staff)").fetchall()
            }
            if not columns:
                raise sqlite3.OperationalError(
                    f"The staff table is missing from {tenant['name']}'s database."
                )
            active_filter = (
                "AND active = 1"
                if active_tenants_only and "active" in columns
                else ""
            )
            rows = connection.execute(
                f"""SELECT id, username FROM staff
                    WHERE username = ? COLLATE NOCASE {active_filter}""",
                (username.strip().lower(),),
            ).fetchall()
        finally:
            connection.close()
        matches.extend(
            {"tenant": tenant, "staff": dict(row)}
            for row in rows
        )
    return matches


def staff_username_is_taken(username, tenant_id=None, staff_id=None):
    return any(
        match["tenant"]["id"] != tenant_id or match["staff"]["id"] != staff_id
        for match in tenant_staff_matches(username, active_tenants_only=False)
    )


def platform_audit(connection, user_id, action, tenant_id=None, details=""):
    connection.execute(
        """INSERT INTO platform_audit(platform_user_id, action, tenant_id, details, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, action, tenant_id, details, now()),
    )


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def db_rows(sql, params=()):
    with database() as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def db_one(sql, params=()):
    rows = db_rows(sql, params)
    return rows[0] if rows else None


def foreign_key_reference_count(connection, target_table, target_id):
    quoted_target = '"' + target_table.replace('"', '""') + '"'
    references = 0
    table_names = [
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    for table_name in table_names:
        quoted_table = '"' + table_name.replace('"', '""') + '"'
        for foreign_key in connection.execute(
            f"PRAGMA foreign_key_list({quoted_table})"
        ):
            if foreign_key["table"] != target_table:
                continue
            quoted_column = '"' + foreign_key["from"].replace('"', '""') + '"'
            references += connection.execute(
                f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} = ?",
                (target_id,),
            ).fetchone()[0]
    return references


def import_test_price_catalog(connection):
    setting_key = "test_price_csv_import_v1"
    if connection.execute(
        "SELECT 1 FROM app_settings WHERE setting_key = ?", (setting_key,)
    ).fetchone():
        return

    catalog_path = Path(__file__).with_name("Test Price.csv")
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Required test catalog was not found: {catalog_path}")

    with catalog_path.open(encoding="cp1252", newline="") as catalog_file:
        rows = list(csv.DictReader(catalog_file))
    if not rows:
        raise ValueError(f"The test catalog is empty: {catalog_path}")

    code_counts = {}
    for row in rows:
        code = (row.get("Test Code") or "").strip().upper()
        if not code:
            raise ValueError("The test catalog contains a row without a test code.")
        code_counts[code] = code_counts.get(code, 0) + 1

    imported_tests = []
    used_codes = set()
    reserved_codes = {code for code, count in code_counts.items() if count == 1}
    skipped_without_price = 0
    for row in rows:
        base_code = row["Test Code"].strip().upper()
        name = (row.get("Test Name") or "").strip()
        department = (row.get("Test Type") or "").strip()
        if not name or not department:
            raise ValueError(f"Test catalog row {row.get('Sl', '?')} has a blank name or type.")

        price_text = (row.get(" Price ") or "").strip().replace(",", "")
        if not price_text:
            skipped_without_price += 1
            continue
        try:
            price = float(price_text)
        except ValueError as error:
            raise ValueError(
                f"Test catalog row {row.get('Sl', '?')} has an invalid price: {price_text!r}."
            ) from error
        if price < 0:
            raise ValueError(f"Test catalog row {row.get('Sl', '?')} has a negative price.")

        row_number = (row.get("Sl") or "").strip()
        code = base_code if code_counts[base_code] == 1 else f"{base_code}-{row_number}"
        if code in used_codes or (code_counts[base_code] > 1 and code in reserved_codes):
            code = f"{base_code}-ROW{row_number}"
            while code in used_codes or code in reserved_codes:
                code += "-X"
        used_codes.add(code)
        imported_tests.append((code, name, department, price))

    if not imported_tests:
        raise ValueError("The test catalog has no rows with a valid price.")

    connection.execute("UPDATE tests SET active = 0")
    connection.executemany(
        """INSERT INTO tests(code, name, department, price, active)
           VALUES (?, ?, ?, ?, 1)
           ON CONFLICT(code) DO UPDATE SET
               name = excluded.name,
               department = excluded.department,
               price = excluded.price,
               active = 1""",
        imported_tests,
    )
    connection.execute(
        "INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?)",
        (
            setting_key,
            f"{catalog_path.name}: imported {len(imported_tests)} priced tests; "
            f"skipped {skipped_without_price} row without a price",
        ),
    )


def initialize_database(db_path=None, allow_create=False):
    selected_path = db_path or st.session_state.get("tenant_db_path")
    if selected_path is None:
        raise RuntimeError("A tenant database context is required for initialization.")
    resolved_path = Path(selected_path)
    if not resolved_path.is_file() and not allow_create:
        raise FileNotFoundError(
            f"Tenant database is missing; restore it from backup: {resolved_path}"
        )
    schema = """
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('Owner', 'Admin', 'Receptionist', 'Cashier', 'Lab Tech')),
        active INTEGER NOT NULL DEFAULT 1,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY,
        patient_code TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL,
        sex TEXT NOT NULL,
        age INTEGER,
        phone TEXT NOT NULL,
        address TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS referrers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        referrer_type TEXT NOT NULL DEFAULT 'Doctor',
        phone TEXT NOT NULL DEFAULT '',
        commission_percent REAL NOT NULL DEFAULT 0 CHECK (commission_percent BETWEEN 0 AND 100),
        commission_type TEXT NOT NULL DEFAULT 'Percentage'
            CHECK (commission_type IN ('Percentage', 'Fixed amount')),
        commission_amount REAL NOT NULL DEFAULT 0 CHECK (commission_amount >= 0),
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        price REAL NOT NULL CHECK (price >= 0),
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY,
        patient_id INTEGER NOT NULL REFERENCES patients(id),
        visit_no TEXT NOT NULL UNIQUE,
        age_value INTEGER NOT NULL DEFAULT 0,
        age_unit TEXT NOT NULL DEFAULT 'years',
        age_days REAL NOT NULL DEFAULT 0,
        sex TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        created_by INTEGER REFERENCES staff(id)
    );
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY,
        visit_id INTEGER NOT NULL UNIQUE REFERENCES visits(id),
        invoice_no TEXT NOT NULL UNIQUE,
        referrer_id INTEGER REFERENCES referrers(id),
        ordered_by_referrer_id INTEGER REFERENCES referrers(id),
        gross REAL NOT NULL CHECK (gross >= 0),
        master_discount_type TEXT NOT NULL DEFAULT '',
        master_discount_value REAL NOT NULL DEFAULT 0,
        discount REAL NOT NULL CHECK (discount >= 0),
        net REAL NOT NULL CHECK (net >= 0),
        paid REAL NOT NULL DEFAULT 0 CHECK (paid >= 0),
        due REAL NOT NULL DEFAULT 0 CHECK (due >= 0),
        refund_due REAL NOT NULL DEFAULT 0 CHECK (refund_due >= 0),
        status TEXT NOT NULL DEFAULT 'Unpaid',
        created_at TEXT NOT NULL,
        created_by INTEGER REFERENCES staff(id)
    );
    CREATE TABLE IF NOT EXISTS invoice_lines (
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id),
        test_id INTEGER NOT NULL REFERENCES tests(id),
        test_name TEXT NOT NULL,
        department TEXT NOT NULL,
        unit_price REAL NOT NULL CHECK (unit_price >= 0),
        discount_type TEXT NOT NULL DEFAULT '',
        discount_value REAL NOT NULL DEFAULT 0,
        discount_amount REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Awaiting collection',
        assigned_to TEXT NOT NULL DEFAULT '',
        assigned_at TEXT,
        cancelled_at TEXT,
        cancelled_by INTEGER REFERENCES staff(id),
        cancellation_reason TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS samples (
        id INTEGER PRIMARY KEY,
        invoice_line_id INTEGER NOT NULL UNIQUE REFERENCES invoice_lines(id),
        sample_code TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'Awaiting collection',
        collected_at TEXT
    );
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY,
        invoice_line_id INTEGER NOT NULL REFERENCES invoice_lines(id),
        status TEXT NOT NULL,
        result_summary TEXT NOT NULL DEFAULT '',
        verified_by TEXT NOT NULL DEFAULT '',
        verified_at TEXT
    );
    CREATE TABLE IF NOT EXISTS report_versions (
        id INTEGER PRIMARY KEY,
        invoice_line_id INTEGER NOT NULL REFERENCES invoice_lines(id),
        result_id INTEGER NOT NULL REFERENCES results(id),
        version INTEGER NOT NULL,
        authorized INTEGER NOT NULL DEFAULT 0,
        issued_by TEXT NOT NULL DEFAULT '',
        issued_at TEXT NOT NULL,
        UNIQUE(invoice_line_id, version)
    );
    CREATE TABLE IF NOT EXISTS report_deliveries (
        id INTEGER PRIMARY KEY,
        report_version_id INTEGER NOT NULL REFERENCES report_versions(id),
        delivered_to TEXT NOT NULL,
        relationship TEXT NOT NULL DEFAULT '',
        delivered_by INTEGER REFERENCES staff(id),
        delivered_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id),
        amount REAL NOT NULL CHECK (amount > 0),
        method TEXT NOT NULL,
        reference TEXT NOT NULL DEFAULT '',
        received_by INTEGER REFERENCES staff(id),
        received_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS day_sessions (
        id INTEGER PRIMARY KEY,
        opened_by INTEGER NOT NULL REFERENCES staff(id),
        opened_at TEXT NOT NULL,
        opening_cash REAL NOT NULL CHECK (opening_cash >= 0),
        closed_by INTEGER REFERENCES staff(id),
        closed_at TEXT,
        expected_cash REAL,
        counted_cash REAL,
        variance REAL,
        notes TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS day_channel_balances (
        id INTEGER PRIMARY KEY,
        day_session_id INTEGER NOT NULL REFERENCES day_sessions(id),
        method TEXT NOT NULL,
        opening_balance REAL NOT NULL DEFAULT 0,
        expected_balance REAL,
        counted_balance REAL,
        variance REAL,
        UNIQUE(day_session_id, method)
    );
    CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY,
        day_session_id INTEGER REFERENCES day_sessions(id),
        direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
        amount REAL NOT NULL CHECK (amount > 0),
        method TEXT NOT NULL,
        entry_type TEXT NOT NULL,
        source_id INTEGER,
        description TEXT NOT NULL,
        created_by INTEGER REFERENCES staff(id),
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER NOT NULL REFERENCES invoices(id),
        day_session_id INTEGER NOT NULL REFERENCES day_sessions(id),
        amount REAL NOT NULL CHECK (amount > 0),
        method TEXT NOT NULL,
        reference TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL,
        paid_by INTEGER REFERENCES staff(id),
        paid_at TEXT NOT NULL,
        retained_amount REAL NOT NULL DEFAULT 0 CHECK (retained_amount >= 0)
    );
    CREATE TABLE IF NOT EXISTS stock_items (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        unit TEXT NOT NULL,
        on_hand REAL NOT NULL DEFAULT 0,
        reorder_level REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY,
        stock_item_id INTEGER NOT NULL REFERENCES stock_items(id),
        quantity REAL NOT NULL CHECK (quantity != 0),
        movement_type TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        created_by INTEGER REFERENCES staff(id),
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS commission_entries (
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER NOT NULL UNIQUE REFERENCES invoices(id),
        referrer_id INTEGER NOT NULL REFERENCES referrers(id),
        amount REAL NOT NULL CHECK (amount >= 0),
        paid_amount REAL NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS billing_sequences (
        name TEXT PRIMARY KEY,
        current_value INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS assignment_history (
        id INTEGER PRIMARY KEY,
        invoice_line_id INTEGER NOT NULL REFERENCES invoice_lines(id),
        old_assignee TEXT NOT NULL,
        new_assignee TEXT NOT NULL,
        reason TEXT NOT NULL,
        changed_by INTEGER REFERENCES staff(id),
        changed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        staff_id INTEGER REFERENCES staff(id),
        acting_role TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        before_value TEXT NOT NULL DEFAULT '',
        after_value TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS referrer_merges (
        id INTEGER PRIMARY KEY,
        source_id INTEGER NOT NULL,
        source_snapshot TEXT NOT NULL,
        target_id INTEGER NOT NULL REFERENCES referrers(id),
        merged_by INTEGER REFERENCES staff(id),
        merged_at TEXT NOT NULL,
        undone_at TEXT,
        undone_by INTEGER REFERENCES staff(id)
    );
    CREATE TABLE IF NOT EXISTS referrer_merge_records (
        id INTEGER PRIMARY KEY,
        merge_id INTEGER NOT NULL REFERENCES referrer_merges(id),
        table_name TEXT NOT NULL,
        column_name TEXT NOT NULL,
        record_id INTEGER NOT NULL
    );
    """
    with database(resolved_path) as connection:
        connection.executescript(schema)
        referrer_columns = {row["name"] for row in connection.execute("PRAGMA table_info(referrers)")}
        if "referrer_type" not in referrer_columns:
            connection.execute(
                "ALTER TABLE referrers ADD COLUMN referrer_type TEXT NOT NULL DEFAULT 'Doctor'"
            )
        referrer_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(referrers)")
        }
        if "commission_type" not in referrer_columns:
            connection.execute(
                """ALTER TABLE referrers
                   ADD COLUMN commission_type TEXT NOT NULL DEFAULT 'Percentage'"""
            )
        if "commission_amount" not in referrer_columns:
            connection.execute(
                """ALTER TABLE referrers
                   ADD COLUMN commission_amount REAL NOT NULL DEFAULT 0
                   CHECK (commission_amount >= 0)"""
            )
        staff_schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'staff'"
        ).fetchone()["sql"]
        if "Lab Tech" not in staff_schema:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """CREATE TABLE staff_rebuilt (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('Owner', 'Admin', 'Receptionist', 'Cashier', 'Lab Tech')),
                    active INTEGER NOT NULL DEFAULT 1,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """INSERT INTO staff_rebuilt(id, username, display_name, password_hash, role, active, created_at)
                   SELECT id, username, display_name, password_hash, role, active, created_at FROM staff"""
            )
            connection.execute("DROP TABLE staff")
            connection.execute("ALTER TABLE staff_rebuilt RENAME TO staff")
            connection.execute("PRAGMA foreign_keys = ON")
        visit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(visits)")}
        for column, definition in (
            ("age_value", "INTEGER NOT NULL DEFAULT 0"),
            ("age_unit", "TEXT NOT NULL DEFAULT 'years'"),
            ("age_days", "REAL NOT NULL DEFAULT 0"),
            ("sex", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in visit_columns:
                connection.execute(f"ALTER TABLE visits ADD COLUMN {column} {definition}")
        invoice_columns = {row["name"] for row in connection.execute("PRAGMA table_info(invoices)")}
        if "ordered_by_referrer_id" not in invoice_columns:
            connection.execute("ALTER TABLE invoices ADD COLUMN ordered_by_referrer_id INTEGER REFERENCES referrers(id)")
        for column, definition in (
            ("master_discount_type", "TEXT NOT NULL DEFAULT ''"),
            ("master_discount_value", "REAL NOT NULL DEFAULT 0"),
        ):
            if column not in invoice_columns:
                connection.execute(f"ALTER TABLE invoices ADD COLUMN {column} {definition}")
        if "refund_due" not in invoice_columns:
            connection.execute(
                "ALTER TABLE invoices ADD COLUMN refund_due REAL NOT NULL DEFAULT 0 CHECK (refund_due >= 0)"
            )
        refund_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(refunds)")
        }
        if "retained_amount" not in refund_columns:
            connection.execute(
                "ALTER TABLE refunds ADD COLUMN retained_amount REAL NOT NULL DEFAULT 0 CHECK (retained_amount >= 0)"
            )
        invoice_line_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(invoice_lines)")
        }
        for column, definition in (
            ("cancelled_at", "TEXT"),
            ("cancelled_by", "INTEGER REFERENCES staff(id)"),
            ("cancellation_reason", "TEXT NOT NULL DEFAULT ''"),
            ("discount_type", "TEXT NOT NULL DEFAULT ''"),
            ("discount_value", "REAL NOT NULL DEFAULT 0"),
            ("discount_amount", "REAL NOT NULL DEFAULT 0"),
        ):
            if column not in invoice_line_columns:
                connection.execute(
                    f"ALTER TABLE invoice_lines ADD COLUMN {column} {definition}"
                )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS unique_payment_reference
               ON payments(reference) WHERE reference <> ''"""
        )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS unique_payment_reference_ci
               ON payments(lower(reference)) WHERE reference <> ''"""
        )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS unique_refund_reference
               ON refunds(reference) WHERE reference <> ''"""
        )
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS unique_refund_reference_ci
               ON refunds(lower(reference)) WHERE reference <> ''"""
        )
        open_day_index = connection.execute(
            """SELECT sql FROM sqlite_master
               WHERE type = 'index' AND name = 'one_open_business_day'"""
        ).fetchone()
        if open_day_index and (
            "(1)" not in open_day_index["sql"]
            or "WHERE closed_at IS NULL" not in open_day_index["sql"]
        ):
            connection.execute("DROP INDEX one_open_business_day")
        connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS one_open_business_day
               ON day_sessions((1)) WHERE closed_at IS NULL"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS visits_created_date
               ON visits(substr(created_at, 1, 10))"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS invoices_created_date
               ON invoices(substr(created_at, 1, 10))"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS payments_received_date
               ON payments(substr(received_at, 1, 10))"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS refunds_paid_date
               ON refunds(substr(paid_at, 1, 10))"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS reports_issued_date
               ON report_versions(substr(issued_at, 1, 10))"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS audit_log_date_id
               ON audit_log(substr(created_at, 1, 10), id DESC)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS audit_log_staff_date
               ON audit_log(staff_id, substr(created_at, 1, 10))"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS invoices_creator_date
               ON invoices(created_by, substr(created_at, 1, 10))"""
        )
        connection.execute(
            "INSERT OR IGNORE INTO billing_sequences(name, current_value) VALUES ('bill', (SELECT COUNT(*) FROM invoices))"
        )
        import_test_price_catalog(connection)
        if connection.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO stock_items(name, unit, on_hand, reorder_level) VALUES (?, ?, ?, ?)",
                [
                    ("EDTA tube", "piece", 30, 10),
                    ("Plain tube", "piece", 25, 10),
                    ("Syringe 5 ml", "piece", 40, 15),
                    ("Gloves", "pair", 20, 8),
                ],
            )
        ensure_accounting_schema(connection)


def password_digest(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 240_000)
    return f"{salt}${digest.hex()}"


def verify_password(password, encoded):
    try:
        salt, expected = encoded.split("$", 1)
        return hmac.compare_digest(password_digest(password, salt).split("$", 1)[1], expected)
    except (ValueError, TypeError):
        return False


def money(amount):
    return f"৳{float(amount or 0):,.2f}"


def money_metric(container, label, amount):
    formatted_amount = money(amount)
    currency, value = formatted_amount[0], formatted_amount[1:]
    container.markdown(
        f"""
        <div data-testid="stMetric">
            <div data-testid="stMetricLabel">{escape(str(label))}</div>
            <div data-testid="stMetricValue">
                <span class="currency-symbol">{currency}</span>{value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def commission_description(referrer):
    if referrer["commission_type"] == "Fixed amount":
        return f"{money(referrer['commission_amount'])} per invoice"
    return f"{float(referrer['commission_percent']):g}%"


def calculate_commission(gross, referrer):
    if referrer["commission_type"] == "Fixed amount":
        return round(float(referrer["commission_amount"]), 2)
    return round(float(gross) * float(referrer["commission_percent"]) / 100, 2)


def cancel_uncollected_test(connection, line_id, reason, staff_id):
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    order = connection.execute(
        """SELECT il.id, il.invoice_id, il.test_name, il.unit_price, il.status,
                  il.assigned_to, i.invoice_no, i.gross, i.discount, i.paid,
                  s.id AS sample_id,
                  (SELECT COUNT(*) FROM results r WHERE r.invoice_line_id = il.id) AS result_count
           FROM invoice_lines il
           JOIN invoices i ON i.id = il.invoice_id
           LEFT JOIN samples s ON s.invoice_line_id = il.id
           WHERE il.id = ?""",
        (line_id,),
    ).fetchone()
    if order is None:
        raise ValueError("The selected billed test no longer exists.")
    if order["status"] != "Awaiting collection" or order["sample_id"] is not None:
        raise ValueError("A test can only be canceled before its sample is collected.")
    if order["result_count"]:
        raise ValueError("A test with a result record cannot be canceled.")
    if not reason.strip():
        raise ValueError("Enter a reason for canceling this test.")
    if order["gross"] <= 0 or order["unit_price"] > order["gross"] + 0.005:
        raise ValueError("The invoice totals are inconsistent; the test cannot be canceled.")

    new_gross = round(max(0.0, order["gross"] - order["unit_price"]), 2)
    remaining_discount_ratio = new_gross / order["gross"]
    new_discount = round(order["discount"] * remaining_discount_ratio, 2)
    new_net = round(max(0.0, new_gross - new_discount), 2)
    new_due = round(max(0.0, new_net - order["paid"]), 2)
    new_refund_due = round(max(0.0, order["paid"] - new_net), 2)
    cancelled_at = now()

    connection.execute(
        """UPDATE invoice_lines
           SET status = 'Cancelled', cancelled_at = ?, cancelled_by = ?, cancellation_reason = ?
           WHERE id = ? AND status = 'Awaiting collection'""",
        (cancelled_at, staff_id, reason.strip(), line_id),
    )
    connection.execute(
        """UPDATE invoices
           SET gross = ?, discount = ?, net = ?, due = ?, refund_due = ?
           WHERE id = ?""",
        (
            new_gross,
            new_discount,
            new_net,
            new_due,
            new_refund_due,
            order["invoice_id"],
        ),
    )
    gross_reversed = round(order["gross"] - new_gross, 2)
    discount_reversed = round(order["discount"] - new_discount, 2)
    receivable_reversed = round(
        (order["gross"] - order["discount"]) - new_net, 2
    )
    cancellation_lines = [
        {
            "account_key": "test_revenue",
            "debit": gross_reversed,
            "description": f"Canceled test · {order['test_name']}",
        }
    ]
    if discount_reversed > 0:
        cancellation_lines.append(
            {
                "account_key": "discount_expense",
                "credit": discount_reversed,
                "description": "Reverse proportional discount",
            }
        )
    if receivable_reversed > 0:
        cancellation_lines.append(
            {
                "account_key": "accounts_receivable",
                "credit": receivable_reversed,
                "description": f"Invoice {order['invoice_no']} reduced",
            }
        )
    post_journal_entry(
        connection,
        cancelled_at[:10],
        f"Test cancellation · {order['invoice_no']} · {order['test_name']}",
        cancellation_lines,
        created_by=staff_id,
        source_type="Test cancellation",
        source_key=f"test-cancellation:{line_id}",
        source_id=line_id,
    )
    commission = connection.execute(
        """SELECT ce.id, ce.referrer_id, ce.amount, ce.paid_amount, r.commission_type,
                  r.commission_percent, r.commission_amount
           FROM commission_entries ce JOIN referrers r ON r.id = ce.referrer_id
           WHERE ce.invoice_id = ?""",
        (order["invoice_id"],),
    ).fetchone()
    if commission:
        referrer = {
            "commission_type": commission["commission_type"],
            "commission_percent": commission["commission_percent"],
            "commission_amount": commission["commission_amount"],
        }
        adjusted_commission = (
            calculate_commission(new_gross, referrer) if new_gross > 0 else 0.0
        )
        updated_commission = max(commission["paid_amount"], adjusted_commission)
        connection.execute(
            "UPDATE commission_entries SET amount = MAX(paid_amount, ?) WHERE id = ?",
            (adjusted_commission, commission["id"]),
        )
        commission_delta = round(updated_commission - commission["amount"], 2)
        if commission_delta:
            if commission_delta > 0:
                commission_lines = [
                    {
                        "account_key": "commission_expense",
                        "debit": commission_delta,
                        "party_type": "Referrer",
                        "party_id": commission["referrer_id"],
                    },
                    {
                        "account_key": "referrer_payable",
                        "credit": commission_delta,
                        "party_type": "Referrer",
                        "party_id": commission["referrer_id"],
                    },
                ]
            else:
                commission_lines = [
                    {
                        "account_key": "referrer_payable",
                        "debit": abs(commission_delta),
                        "party_type": "Referrer",
                        "party_id": commission["referrer_id"],
                    },
                    {
                        "account_key": "commission_expense",
                        "credit": abs(commission_delta),
                        "party_type": "Referrer",
                        "party_id": commission["referrer_id"],
                    },
                ]
            post_journal_entry(
                connection,
                cancelled_at[:10],
                f"Commission adjustment · {order['invoice_no']}",
                commission_lines,
                created_by=staff_id,
                source_type="Commission adjustment",
                source_key=f"commission-adjustment:{line_id}",
                source_id=commission["id"],
            )

    audit(
        connection,
        staff_id,
        "Billed test canceled before collection",
        "test_line",
        line_id,
        f"status={order['status']}; gross={order['gross']:.2f}; "
        f"discount={order['discount']:.2f}; net={order['gross'] - order['discount']:.2f}",
        f"test={order['test_name']}; reason={reason.strip()}; "
        f"gross={new_gross:.2f}; discount={new_discount:.2f}; net={new_net:.2f}; "
        f"refund_due={new_refund_due:.2f}",
    )
    return {
        "invoice_no": order["invoice_no"],
        "test_name": order["test_name"],
        "new_net": new_net,
        "refund_due": new_refund_due,
    }


def collect_lab_sample(connection, line_id, staff_id, invoice_no, test_name):
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    current_line = connection.execute(
        "SELECT status FROM invoice_lines WHERE id = ?",
        (line_id,),
    ).fetchone()
    existing_sample = connection.execute(
        "SELECT id FROM samples WHERE invoice_line_id = ?",
        (line_id,),
    ).fetchone()
    if (
        current_line is None
        or current_line["status"] != "Awaiting collection"
        or existing_sample is not None
    ):
        raise ValueError("This test was changed or canceled before collection.")
    sample_code = f"SMP-{datetime.now():%y%m%d}-{line_id:06d}"
    cursor = connection.execute(
        """INSERT INTO samples(invoice_line_id, sample_code, status, collected_at)
           VALUES (?, ?, 'Collected', ?)""",
        (line_id, sample_code, now()),
    )
    connection.execute(
        "UPDATE invoice_lines SET status = 'In progress' WHERE id = ?",
        (line_id,),
    )
    audit(
        connection,
        staff_id,
        "Sample collected",
        "sample",
        cursor.lastrowid,
        "",
        f"{sample_code}; invoice={invoice_no}; test={test_name}",
    )
    return sample_code


def printable_report_html(report):
    result = escape(str(report["result_summary"] or "")).replace("\n", "<br>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(str(report['invoice_no']))} · {escape(str(report['test_name']))} · Report v{report['version']}</title>
<style>
body {{ max-width: 800px; margin: 2rem auto; padding: 1.5rem; color: #17383a; font: 16px Arial, sans-serif; }}
header {{ border-bottom: 3px solid #005b60; margin-bottom: 1.5rem; padding-bottom: 1rem; }}
h1 {{ color: #005b60; margin-bottom: .35rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1.25rem 0; }}
th, td {{ border: 1px solid #c9d8da; padding: .65rem; text-align: left; vertical-align: top; }}
.result {{ min-height: 7rem; white-space: normal; }}
.authorization {{ margin-top: 2rem; color: #40595b; font-size: .9rem; }}
@media print {{ body {{ margin: 0; max-width: none; }} }}
</style>
</head>
<body>
<header>
<h1>{escape(APP_NAME)}</h1>
<div>Diagnostic laboratory report · Version {report['version']}</div>
</header>
<table>
<tr><th>Patient</th><td>{escape(str(report['full_name']))}</td><th>Patient ID</th><td>{escape(str(report['patient_code']))}</td></tr>
<tr><th>Age</th><td>{escape(str(report['age_value']))} {escape(str(report['age_unit']))}</td><th>Sex</th><td>{escape(str(report['sex']))}</td></tr>
<tr><th>Invoice</th><td>{escape(str(report['invoice_no']))}</td><th>Sample</th><td>{escape(str(report['sample_code'] or '—'))}</td></tr>
<tr><th>Test</th><td>{escape(str(report['test_name']))}</td><th>Department</th><td>{escape(str(report['department']))}</td></tr>
</table>
<h2>Result / observations</h2>
<div class="result">{result}</div>
<div class="authorization">
Verified by {escape(str(report['verified_by'] or '—'))}
{f" on {escape(str(report['verified_at']))}" if report['verified_at'] else ""}<br>
Authorized by {escape(str(report['issued_by'] or '—'))} on {escape(str(report['issued_at']))}
</div>
</body>
</html>"""


def current_session():
    return db_one("SELECT * FROM day_sessions WHERE closed_at IS NULL ORDER BY id DESC LIMIT 1")


def add_payment(connection, invoice, amount, method, reference, staff_id, session_id):
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    current_invoice = connection.execute(
        "SELECT due, status FROM invoices WHERE id = ?", (invoice["id"],)
    ).fetchone()
    if current_invoice is None or current_invoice["status"] != "Confirmed":
        raise ValueError("Payments can only be recorded against a confirmed bill.")
    if amount > current_invoice["due"] + 0.005:
        raise ValueError("The payment exceeds the remaining balance.")
    if method in REFERENCE_REQUIRED_METHODS and not reference.strip():
        raise ValueError(f"A transaction number is required for {method} payments.")
    if reference.strip() and connection.execute(
        "SELECT 1 FROM payments WHERE lower(reference) = lower(?)", (reference.strip(),)
    ).fetchone():
        raise ValueError("This transaction number has already been used.")
    received_at = now()
    cursor = connection.execute(
        """INSERT INTO payments(invoice_id, amount, method, reference, received_by, received_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (invoice["id"], amount, method, reference.strip(), staff_id, received_at),
    )
    payment_id = cursor.lastrowid
    connection.execute(
        "UPDATE invoices SET paid = paid + ?, due = MAX(0, due - ?) WHERE id = ?",
        (amount, amount, invoice["id"]),
    )
    connection.execute(
        """INSERT INTO ledger(day_session_id, direction, amount, method, entry_type, source_id,
                              description, created_by, created_at)
           VALUES (?, 'in', ?, ?, 'Payment', ?, ?, ?, ?)""",
        (session_id, amount, method, payment_id, f"Invoice {invoice['invoice_no']}", staff_id, received_at),
    )
    post_journal_entry(
        connection,
        received_at[:10],
        f"Payment received · {invoice['invoice_no']}",
        [
            {
                "account_key": cash_account_key(method),
                "debit": amount,
                "description": f"{method} receipt",
            },
            {
                "account_key": "accounts_receivable",
                "credit": amount,
                "description": f"Invoice {invoice['invoice_no']}",
            },
        ],
        created_by=staff_id,
        source_type="Payment",
        source_key=f"payment:{payment_id}",
        source_id=payment_id,
    )
    audit(
        connection,
        staff_id,
        "Payment received",
        "payment",
        payment_id,
        "",
        f"invoice={invoice['invoice_no']}; amount={amount:.2f}; method={method}; reference={reference.strip()}",
    )


def issue_patient_refund(
    connection, invoice_id, amount, method, reference, reason, staff_id, session_id,
    retain_remaining_as_income=False,
):
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    session = connection.execute(
        "SELECT id FROM day_sessions WHERE id = ? AND closed_at IS NULL",
        (session_id,),
    ).fetchone()
    if session is None:
        raise ValueError("Open a cashier day before issuing a patient refund.")
    invoice = connection.execute(
        """SELECT i.id, i.invoice_no, i.refund_due, p.full_name, p.patient_code
           FROM invoices i JOIN visits v ON v.id = i.visit_id
           JOIN patients p ON p.id = v.patient_id
           WHERE i.id = ?""",
        (invoice_id,),
    ).fetchone()
    if invoice is None or invoice["refund_due"] <= 0:
        raise ValueError("This invoice has no remaining patient refund due.")
    if amount <= 0 or amount > invoice["refund_due"] + 0.005:
        raise ValueError("Refund amount must be positive and no greater than the refund due.")
    retained_amount = (
        round(max(0.0, invoice["refund_due"] - amount), 2)
        if retain_remaining_as_income
        else 0.0
    )
    if method not in PAYMENT_METHODS:
        raise ValueError("Select a valid refund payment method.")
    if method in REFERENCE_REQUIRED_METHODS and not reference.strip():
        raise ValueError(f"A transaction number is required for {method} refunds.")
    if not reason.strip():
        raise ValueError("Enter a reason for the refund.")
    if reference.strip():
        used_reference = connection.execute(
            """SELECT 1 FROM payments WHERE lower(reference) = lower(?)
               UNION ALL
               SELECT 1 FROM refunds WHERE lower(reference) = lower(?)
               LIMIT 1""",
            (reference.strip(), reference.strip()),
        ).fetchone()
        if used_reference:
            raise ValueError("This transaction number has already been used.")

    refunded_at = now()
    cursor = connection.execute(
        """INSERT INTO refunds(invoice_id, day_session_id, amount, method, reference,
                               reason, paid_by, paid_at, retained_amount)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            invoice_id,
            session_id,
            amount,
            method,
            reference.strip(),
            reason.strip(),
            staff_id,
            refunded_at,
            retained_amount,
        ),
    )
    refund_id = cursor.lastrowid
    connection.execute(
        """UPDATE invoices
           SET refund_due = MAX(0, refund_due - ?)
           WHERE id = ? AND refund_due + 0.005 >= ?""",
        (amount + retained_amount, invoice_id, amount + retained_amount),
    )
    connection.execute(
        """INSERT INTO ledger(day_session_id, direction, amount, method, entry_type, source_id,
                              description, created_by, created_at)
           VALUES (?, 'out', ?, ?, 'Refund', ?, ?, ?, ?)""",
        (
            session_id,
            amount,
            method,
            refund_id,
            f"Patient refund {invoice['invoice_no']} · {invoice['full_name']} · {reason.strip()}",
            staff_id,
            refunded_at,
        ),
    )
    refund_lines = [
        {
            "account_key": "accounts_receivable",
            "debit": amount + retained_amount,
            "description": f"Patient refund {invoice['invoice_no']}",
        },
        {
            "account_key": cash_account_key(method),
            "credit": amount,
            "description": f"Refund paid by {method}",
        },
    ]
    if retained_amount:
        refund_lines.append(
            {
                "account_key": "cancellation_income",
                "credit": retained_amount,
                "description": "Unpaid refund balance retained as income",
            }
        )
    post_journal_entry(
        connection,
        refunded_at[:10],
        f"Patient refund · {invoice['invoice_no']}",
        refund_lines,
        created_by=staff_id,
        source_type="Refund",
        source_key=f"refund:{refund_id}",
        source_id=refund_id,
    )
    audit(
        connection,
        staff_id,
        "Patient refund issued",
        "refund",
        refund_id,
        f"invoice={invoice['invoice_no']}; refund_due={invoice['refund_due']:.2f}",
        f"amount={amount:.2f}; retained_as_income={retained_amount:.2f}; "
        f"method={method}; reference={reference.strip()}; reason={reason.strip()}",
    )
    return {
        "refund_id": refund_id,
        "invoice_no": invoice["invoice_no"],
        "patient_name": invoice["full_name"],
        "patient_code": invoice["patient_code"],
        "amount": amount,
        "retained_amount": retained_amount,
    }


def audit(
    connection, staff_id, action, entity_type, entity_id,
    before_value="", after_value="", acting_role_override=None
):
    user = connection.execute("SELECT role FROM staff WHERE id = ?", (staff_id,)).fetchone()
    acting_role = acting_role_override or (user["role"] if user else "Unknown")
    dev_actor = st.session_state.get("tenant_dev_actor")
    if dev_actor:
        acting_role = f"Platform Dev ({dev_actor})"
    connection.execute(
        """INSERT INTO audit_log(staff_id, acting_role, action, entity_type, entity_id,
                                 before_value, after_value, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (staff_id, acting_role, action, entity_type, str(entity_id),
         str(before_value), str(after_value), now()),
    )


def generate_totp_secret():
    return secrets.token_bytes(20)


def encode_totp_secret(secret):
    import base64

    return base64.b32encode(secret).decode("ascii").rstrip("=")


def totp_counter_code(secret, counter):
    import base64
    import struct

    padded_secret = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def matching_totp_counter(secret, code, last_counter=0):
    if not code.isdigit() or len(code) != 6:
        return None
    current_counter = int(time.time() // 30)
    for counter in (current_counter, current_counter - 1, current_counter + 1):
        if counter > last_counter and hmac.compare_digest(
            totp_counter_code(secret, counter), code
        ):
            return counter
    return None


def dev_user_count():
    with platform_database() as connection:
        return connection.execute("SELECT COUNT(*) FROM platform_users").fetchone()[0]


def dev_bootstrap_screen():
    st.subheader("Create the platform Dev account")
    setup_token = os.environ.get("MEDSCOPE_DEV_SETUP_TOKEN", "")
    if not setup_token:
        st.warning(
            "Dev setup is locked until MEDSCOPE_DEV_SETUP_TOKEN is set in the server environment."
        )
        st.caption(
            "Stop the current server with Ctrl+C. Run these commands in the same PowerShell "
            "window, then enter the printed token here:"
        )
        st.code(
            '$env:MEDSCOPE_DEV_SETUP_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")\n'
            "$env:MEDSCOPE_DEV_SETUP_TOKEN\n"
            'python -m streamlit run "DCMS V1.py" --server.address 127.0.0.1 '
            "--server.port 8501 --server.headless true --browser.gatherUsageStats false",
            language="powershell",
        )
        return
    with st.form("platform_dev_bootstrap", clear_on_submit=True):
        token = st.text_input("One-time setup token", type="password")
        display_name = st.text_input("Developer name")
        username = st.text_input("Developer username")
        password = st.text_input(
            "Strong Dev password",
            type="password",
            help="Use at least 12 characters; this is separate from tenant PINs.",
        )
        confirm_password = st.text_input("Confirm Dev password", type="password")
        submitted = st.form_submit_button("Generate authenticator setup", type="primary")
    if submitted:
        if not hmac.compare_digest(token, setup_token):
            st.error("The setup token is invalid.")
        elif not display_name.strip() or not username.strip():
            st.error("Enter a developer name and username.")
        elif len(password) < 12:
            st.error("The Dev password must be at least 12 characters.")
        elif password != confirm_password:
            st.error("The passwords do not match.")
        elif dev_user_count():
            st.error("The platform Dev account has already been created.")
        else:
            secret = encode_totp_secret(generate_totp_secret())
            st.session_state["pending_dev_setup"] = {
                "display_name": display_name.strip(),
                "username": username.strip().lower(),
                "password_hash": password_digest(password),
                "totp_secret": secret,
            }
            st.rerun()

    pending = st.session_state.get("pending_dev_setup")
    if pending:
        issuer = quote(APP_NAME)
        account = quote(pending["username"])
        st.info(
            "Add this secret to an authenticator app as a time-based one-time password, "
            "then enter the current six-digit code below. Keep the secret private."
        )
        st.code(pending["totp_secret"])
        st.code(
            f"otpauth://totp/{issuer}:{account}?secret={pending['totp_secret']}"
            f"&issuer={issuer}&digits=6&period=30",
            language="text",
        )
        with st.form("confirm_platform_dev_mfa", clear_on_submit=True):
            verification_code = st.text_input("Authenticator code", max_chars=6)
            confirm_setup = st.form_submit_button("Confirm MFA and create Dev account")
        if confirm_setup:
            counter = matching_totp_counter(pending["totp_secret"], verification_code)
            if counter is None:
                st.error("The authenticator code is invalid or expired.")
            else:
                try:
                    with platform_database() as connection:
                        if connection.execute(
                            "SELECT COUNT(*) FROM platform_users"
                        ).fetchone()[0]:
                            raise ValueError("A platform Dev account already exists.")
                        cursor = connection.execute(
                            """INSERT INTO platform_users(
                                   username, display_name, password_hash, totp_secret,
                                   last_totp_counter, created_at
                               ) VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                pending["username"],
                                pending["display_name"],
                                pending["password_hash"],
                                pending["totp_secret"],
                                counter,
                                now(),
                            ),
                        )
                        platform_audit(
                            connection,
                            cursor.lastrowid,
                            "Platform Dev account created",
                            details=pending["username"],
                        )
                    st.session_state.pop("pending_dev_setup", None)
                    st.success("Dev account created with authenticator MFA. Sign in to continue.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That Dev username is already in use.")
                except ValueError as error:
                    st.error(str(error))


def platform_user_by_username(username):
    with platform_database() as connection:
        row = connection.execute(
            """SELECT * FROM platform_users
               WHERE username = ? COLLATE NOCASE""",
            (username.strip().lower(),),
        ).fetchone()
    return dict(row) if row else None


def developer_login(username, password, code):
    with platform_database() as connection:
        user = connection.execute(
            """SELECT * FROM platform_users
               WHERE username = ? COLLATE NOCASE AND active = 1""",
            (username.strip().lower(),),
        ).fetchone()
        if user is None:
            st.error("Dev credentials or authenticator code are invalid.")
            return
        if user["locked"]:
            st.error("This Dev account is locked. Contact the platform administrator.")
            return
        counter = matching_totp_counter(
            user["totp_secret"], code, user["last_totp_counter"]
        )
        if not verify_password(password, user["password_hash"]) or counter is None:
            attempts = min(5, int(user["failed_attempts"]) + 1)
            connection.execute(
                "UPDATE platform_users SET failed_attempts = ?, locked = ? WHERE id = ?",
                (attempts, int(attempts >= 5), user["id"]),
            )
            st.error(
                "Dev credentials or authenticator code are invalid."
                if attempts < 5
                else "This Dev account is locked after five failed attempts."
            )
            return
        connection.execute(
            """UPDATE platform_users SET failed_attempts = 0, last_totp_counter = ?
               WHERE id = ?""",
            (counter, user["id"]),
        )
        platform_audit(
            connection,
            user["id"],
            "Platform Dev signed in",
            details="MFA verified",
        )
    st.session_state["platform_dev"] = {
        "id": user["id"],
        "username": user["username"],
        "name": user["display_name"],
    }
    st.session_state["platform_dev_authenticated_at"] = time.time()
    st.rerun()


def tenant_staff_login(username, password):
    if not username.strip() or not password:
        st.error("Enter your username and PIN.")
        return
    try:
        matches = tenant_staff_matches(username)
    except (RuntimeError, sqlite3.Error) as error:
        st.error(f"Unable to verify sign-in: {error}")
        return
    if len(matches) != 1:
        st.error("Username or PIN is incorrect.")
        return

    tenant = matches[0]["tenant"]
    staff = matches[0]["staff"]
    tenant_path = tenant_database_path(tenant["id"])
    with platform_database() as connection:
        current_tenant = connection.execute(
            "SELECT active FROM tenants WHERE id = ?",
            (tenant["id"],),
        ).fetchone()
    if current_tenant is None or not current_tenant["active"]:
        st.error("This diagnostic center is disabled. Contact MedScope Dev.")
        return

    try:
        initialize_database(tenant_path)
    except (FileNotFoundError, sqlite3.Error) as error:
        st.error(f"Unable to open the diagnostic center: {error}")
        return
    with database(tenant_path) as connection:
        staff = connection.execute(
            "SELECT * FROM staff WHERE username = ? COLLATE NOCASE AND active = 1",
            (staff["username"],),
        ).fetchone()
        if staff:
            staff = dict(staff)
    if staff is None:
        st.error("Username or PIN is incorrect.")
    elif staff["locked"]:
        st.error(
            "This account is locked after five incorrect PIN attempts. "
            "Ask an Owner/Admin to reset it."
        )
    elif verify_password(password, staff["password_hash"]):
        with database(tenant_path) as connection:
            connection.execute(
                "UPDATE staff SET failed_attempts = 0 WHERE id = ?",
                (staff["id"],),
            )
        st.session_state["tenant_id"] = tenant["id"]
        st.session_state["tenant_db_path"] = str(tenant_path)
        st.session_state["staff"] = {
            "id": staff["id"],
            "name": staff["display_name"],
            "username": staff["username"],
            "role": staff["role"],
        }
        st.session_state.pop("platform_dev", None)
        st.session_state.pop("tenant_dev_actor", None)
        st.rerun()
    else:
        attempts = min(5, int(staff["failed_attempts"]) + 1)
        with database(tenant_path) as connection:
            connection.execute(
                "UPDATE staff SET failed_attempts = ?, locked = ? WHERE id = ?",
                (attempts, int(attempts >= 5), staff["id"]),
            )
        st.error(
            "Incorrect PIN. This account is locked after five failed attempts."
            if attempts >= 5
            else "Username or PIN is incorrect."
        )


def login_screen():
    with st.container(key="login_screen"):
        branding, sign_in = st.columns([1.25, 1], gap="large")
        with branding:
            st.title(f"✚ {APP_NAME}")
            st.caption("Diagnostic Center Management System")
        with sign_in:
            with st.form("unified_sign_in_form"):
                username = st.text_input("Username", key="login_username")
                dev_user = platform_user_by_username(username) if username.strip() else None
                is_master_id = dev_user is not None
                credential = st.text_input(
                    "Dev password" if is_master_id else "Password / PIN",
                    type="password",
                    key="login_credential",
                )
                tenant_matches = []
                if username.strip() and not is_master_id:
                    try:
                        tenant_matches = tenant_staff_matches(username)
                    except (RuntimeError, sqlite3.Error) as error:
                        st.error(f"Unable to look up the diagnostic center: {error}")
                    else:
                        if len(tenant_matches) == 1:
                            st.info(f"Diagnostic center: **{tenant_matches[0]['tenant']['name']}**")
                        elif len(tenant_matches) > 1:
                            st.error(
                                "This username matches more than one diagnostic center. "
                                "Contact MedScope Dev to resolve the duplicate."
                            )
                if is_master_id:
                    st.info(
                        "Master / Dev ID detected. Enter the authenticator code to sign in; "
                        "tenant switching becomes available after verification."
                    )
                    authenticator_code = st.text_input(
                        "Authenticator code",
                        max_chars=6,
                        key="login_authenticator_code",
                    )
                else:
                    authenticator_code = ""

                submit_label = "Authenticate" if is_master_id else "Sign in"
                submitted = st.form_submit_button(
                    submit_label,
                    type="primary",
                    use_container_width=True,
                )
            if submitted:
                if not username.strip():
                    st.error("Enter your username.")
                elif is_master_id:
                    if not credential or not authenticator_code:
                        st.error("Enter your Dev password and authenticator code.")
                    elif not dev_user["active"]:
                        st.error("This Dev account is disabled.")
                    else:
                        developer_login(username, credential, authenticator_code)
                elif len(tenant_matches) == 1:
                    tenant_staff_login(username, credential)
                elif not tenant_matches:
                    st.error("Username or PIN is incorrect.")

            if dev_user_count() == 0:
                with st.expander("First-time platform Dev setup"):
                    dev_bootstrap_screen()


def dashboard(staff):
    if staff["role"] == "Owner":
        owner_dashboard(staff)
        return
    if staff["role"] == "Admin":
        admin_dashboard(staff)
        return
    if staff["role"] == "Lab Tech":
        lab_tech_dashboard(staff)
        return

    today = datetime.now().astimezone().date().isoformat()
    metrics_data = db_one(
        """SELECT
             (SELECT COUNT(*) FROM visits
              WHERE substr(created_at, 1, 10) = ?) AS patient_count,
             (SELECT COUNT(*) FROM invoice_lines
              WHERE status != 'Cancelled'
                AND (status = 'Awaiting collection' OR assigned_to = '')) AS pending_count,
             (SELECT COALESCE(SUM(due), 0) FROM invoices WHERE due > 0) AS dues,
             (SELECT COUNT(*) FROM stock_items
              WHERE on_hand <= reorder_level) AS stock_alerts""",
        (today,),
    )
    patient_count = metrics_data["patient_count"]
    pending_count = metrics_data["pending_count"]
    dues = metrics_data["dues"]
    stock_alerts = metrics_data["stock_alerts"]
    issues = pending_count + stock_alerts
    st.title("Receptionist Dashboard")
    st.caption("Patient intake · Billing · Referral entry · Front-desk operations")
    cols = st.columns(4)
    cols[0].metric("Today's Patients", patient_count)
    cols[1].metric("Tests Pending", pending_count)
    money_metric(cols[2], "Outstanding Dues", dues)
    cols[3].metric("Open Issues", issues)

    st.markdown("#### Front Desk")
    cards = [
        ("Find Patient", "Search by patient ID, name or contact and view visit history"),
        ("New Invoice", "Register a patient, tests, referrer and payment"),
        ("Invoices", "Search, view and reprint receipts"),
        ("Dues", "Find balances and record payments"),
        ("Test Assignment", "Track samples and assign departments"),
        ("Report Delivery", "Release only authorized reports"),
        ("Inventory", "Record stock and low-stock alerts"),
        ("Accounts & Referrers", "Manage access and referral commission"),
        ("Day Open / Close", "Open cash float and reconcile the shift"),
    ]
    if staff["role"] not in ("Owner", "Admin"):
        cards = [card for card in cards if card[0] != "Accounts & Referrers"]
    if staff["role"] == "Admin":
        cards.append(("Audit Trail", "Search recorded staff and system actions"))
    if staff["role"] == "Owner":
        cards.extend(
            [
                ("Reports", "Review user, test, financial and commission reports"),
                ("Audit Trail", "Search recorded staff and system actions"),
            ]
        )
    for row_start in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, (title, description) in zip(columns, cards[row_start:row_start + 4]):
            with column:
                st.button(
                    title,
                    key=f"dashboard_nav_{title}",
                    use_container_width=True,
                    on_click=go_to_page,
                    args=(title,),
                )
                st.caption(description)
    st.divider()
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Recent invoices")
        recent = db_rows(
            """SELECT i.invoice_no, p.full_name, i.net, i.paid, i.due, i.status, i.created_at
               FROM invoices i JOIN visits v ON v.id = i.visit_id
               JOIN patients p ON p.id = v.patient_id ORDER BY i.id DESC LIMIT 8"""
        )
        if recent:
            st.dataframe(recent, hide_index=True, use_container_width=True)
        else:
            st.caption("No invoices yet. Start with New Invoice.")
    with right:
        st.subheader("Shift status")
        session = current_session()
        if session:
            st.success(f"Open since {session['opened_at']} · Opening cash {money(session['opening_cash'])}")
        else:
            st.warning("No open cashier shift. Open the day before receiving payments.")
        if stock_alerts:
            st.warning(f"{stock_alerts} stock item(s) are at or below reorder level.")
        if issues:
            st.caption("Open issues include tests awaiting collection/assignment and low-stock items.")


def owner_dashboard(staff):
    today = datetime.now().astimezone().date().isoformat()
    metrics_data = db_one(
        """SELECT
             (SELECT COALESCE(SUM(net), 0) FROM invoices
              WHERE substr(created_at, 1, 10) = ?) AS gross_today,
             (SELECT COALESCE(SUM(amount), 0) FROM payments
              WHERE substr(received_at, 1, 10) = ?) AS received_today,
             (SELECT COALESCE(SUM(due), 0) FROM invoices WHERE due > 0) AS outstanding,
             (SELECT COALESCE(SUM(refund_due), 0) FROM invoices
              WHERE refund_due > 0) AS patient_credits_due,
             (SELECT COALESCE(SUM(retained_amount), 0) FROM refunds
              WHERE substr(paid_at, 1, 10) = ?) AS cancellation_income_today,
             (SELECT COALESCE(SUM(amount - paid_amount), 0)
              FROM commission_entries) AS commission_due,
             (SELECT COUNT(*) FROM staff WHERE active = 1) AS active_staff,
             (SELECT COUNT(*) FROM stock_items
              WHERE on_hand <= reorder_level) AS stock_alerts""",
        (today, today, today),
    )
    gross_today = metrics_data["gross_today"]
    received_today = metrics_data["received_today"]
    outstanding = metrics_data["outstanding"]
    patient_credits_due = metrics_data["patient_credits_due"]
    cancellation_income_today = metrics_data["cancellation_income_today"]
    commission_due = metrics_data["commission_due"]
    active_staff = metrics_data["active_staff"]
    open_session = current_session()
    stock_alerts = metrics_data["stock_alerts"]

    st.title("Owner Dashboard")
    st.caption("Financial control · User access · Center-wide operations")
    metrics = st.columns(6)
    money_metric(metrics[0], "Billed today", gross_today)
    money_metric(metrics[1], "Received today", received_today)
    money_metric(metrics[2], "Outstanding dues", outstanding)
    money_metric(metrics[3], "Patient credits / refunds", patient_credits_due)
    money_metric(metrics[4], "Cancellation income retained today", cancellation_income_today)
    money_metric(metrics[5], "Commission payable", commission_due)

    st.subheader("Owner controls")
    controls = [
        ("Accounts & Referrers", "Manage users, catalog and referral settings"),
        ("Day Open / Close", "Review cashier shift and reconcile the day"),
        ("Invoices", "Review bills and payment history"),
        ("Inventory", "Check stock and authorize corrections"),
        ("Lab Work", "Monitor samples, results and report authorization"),
        ("Report Delivery", "Review released reports and handover history"),
        ("Reports", "Review staff, test, financial and commission activity"),
        ("Audit Trail", "Search tenant actions and record changes"),
        ("Accounting", "Manage journals, financial statements, payables and assets"),
    ]
    for row_start in range(0, len(controls), 3):
        columns = st.columns(3)
        for column, (title, description) in zip(columns, controls[row_start:row_start + 3]):
            with column:
                st.button(
                    title,
                    key=f"owner_dashboard_nav_{title}",
                    use_container_width=True,
                    on_click=go_to_page,
                    args=(title,),
                )
                st.caption(description)

    operations, status = st.columns([1.4, 1])
    with operations:
        st.subheader("Recent business activity")
        recent_activity = db_rows(
            """SELECT a.created_at, s.display_name, a.acting_role, a.action,
                      a.entity_type, a.entity_id
               FROM audit_log a LEFT JOIN staff s ON s.id = a.staff_id
               ORDER BY a.id DESC LIMIT 10"""
        )
        if recent_activity:
            st.dataframe(recent_activity, hide_index=True, use_container_width=True)
        else:
            st.caption("No activity has been recorded yet.")
    with status:
        st.subheader("Center status")
        st.metric("Active user accounts", active_staff)
        if open_session:
            st.success(f"Cashier day open since {open_session['opened_at']}.")
        else:
            st.warning("No cashier day is currently open.")
        if stock_alerts:
            st.warning(f"{stock_alerts} stock item(s) are at or below reorder level.")


def admin_dashboard(staff):
    today = datetime.now().astimezone().date().isoformat()
    metrics_data = db_one(
        """SELECT
             (SELECT COUNT(*) FROM visits
              WHERE substr(created_at, 1, 10) = ?) AS patients_today,
             (SELECT COUNT(*) FROM invoice_lines il
              LEFT JOIN samples s ON s.invoice_line_id = il.id
              WHERE s.id IS NULL AND il.status != 'Cancelled') AS pending_collection,
             (SELECT COUNT(*) FROM samples s
              JOIN invoice_lines il ON il.id = s.invoice_line_id
              WHERE s.status = 'Collected'
                AND NOT EXISTS (
                    SELECT 1 FROM results r WHERE r.invoice_line_id = il.id
                )) AS pending_results,
             (SELECT COUNT(*) FROM results
              WHERE status = 'Pending verification') AS pending_verification,
             (SELECT COALESCE(SUM(due), 0) FROM invoices
              WHERE due > 0) AS outstanding,
             (SELECT COALESCE(SUM(amount), 0) FROM payments
              WHERE substr(received_at, 1, 10) = ?) AS payments_today,
             (SELECT COUNT(*) FROM stock_items
              WHERE on_hand <= reorder_level) AS stock_alerts""",
        (today, today),
    )
    patients_today = metrics_data["patients_today"]
    pending_collection = metrics_data["pending_collection"]
    pending_results = metrics_data["pending_results"]
    pending_verification = metrics_data["pending_verification"]
    outstanding = metrics_data["outstanding"]
    payments_today = metrics_data["payments_today"]
    stock_alerts = metrics_data["stock_alerts"]
    st.title("Admin Dashboard")
    st.caption("Center operations · Staff and catalog control · Financial oversight")
    metrics = st.columns(5)
    metrics[0].metric("Patients today", patients_today)
    metrics[1].metric("Awaiting collection", pending_collection)
    metrics[2].metric("Awaiting results", pending_results)
    metrics[3].metric("Awaiting verification", pending_verification)
    metrics[4].metric("Stock alerts", stock_alerts)
    finance = st.columns(2)
    money_metric(finance[0], "Payments received today", payments_today)
    money_metric(finance[1], "Outstanding dues", outstanding)

    st.subheader("Operations")
    cards = [
        ("Find Patient", "Patient records and visit history"),
        ("New Invoice", "Register patients and bill tests"),
        ("Invoices", "Search invoices and reprint receipts"),
        ("Dues", "Outstanding balances and payments"),
        ("Test Assignment", "Route tests and review assignments"),
        ("Lab Work", "Monitor collection and result processing"),
        ("Report Delivery", "Release authorized reports"),
        ("Inventory", "Stock levels and movements"),
        ("Accounts & Referrers", "Manage staff, tests and referrers"),
        ("Day Open / Close", "Cashier shift and day reconciliation"),
    ]
    for row_start in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, (title, description) in zip(columns, cards[row_start:row_start + 4]):
            with column:
                st.button(
                    title,
                    key=f"dashboard_nav_{title}",
                    use_container_width=True,
                    on_click=go_to_page,
                    args=(title,),
                )
                st.caption(description)

    activity, alerts = st.columns([1.4, 1])
    with activity:
        st.subheader("Recent activity")
        recent_activity = db_rows(
            """SELECT a.created_at, s.display_name, a.acting_role, a.action,
                      a.entity_type, a.entity_id
               FROM audit_log a LEFT JOIN staff s ON s.id = a.staff_id
               ORDER BY a.id DESC LIMIT 10"""
        )
        if recent_activity:
            st.dataframe(recent_activity, hide_index=True, use_container_width=True)
        else:
            st.caption("No activity has been recorded yet.")
    with alerts:
        st.subheader("Needs attention")
        open_session = current_session()
        if not open_session:
            st.warning("No cashier shift is currently open.")
        if pending_collection:
            st.info(f"{pending_collection} billed test(s) are awaiting sample collection.")
        if pending_results:
            st.info(f"{pending_results} collected sample(s) are awaiting result entry.")
        if pending_verification:
            st.info(f"{pending_verification} result(s) are awaiting verification.")
        if stock_alerts:
            st.warning(f"{stock_alerts} stock item(s) are at or below reorder level.")
        if not any((not open_session, pending_collection, pending_results, pending_verification, stock_alerts)):
            st.success("No operational alerts.")


def lab_work_orders():
    return db_rows(
        """SELECT il.id AS line_id, i.invoice_no, p.full_name, p.patient_code,
                  v.age_value, v.age_unit, v.sex, il.test_name, il.department,
                  il.status AS line_status, s.id AS sample_id, s.sample_code,
                  COALESCE(s.status, 'Awaiting collection') AS sample_status,
                  (SELECT r.id FROM results r WHERE r.invoice_line_id = il.id
                   ORDER BY r.id DESC LIMIT 1) AS result_id,
                  (SELECT r.status FROM results r WHERE r.invoice_line_id = il.id
                   ORDER BY r.id DESC LIMIT 1) AS result_status,
                  (SELECT r.result_summary FROM results r WHERE r.invoice_line_id = il.id
                   ORDER BY r.id DESC LIMIT 1) AS result_summary
           FROM invoice_lines il
           JOIN invoices i ON i.id = il.invoice_id
           JOIN visits v ON v.id = i.visit_id
           JOIN patients p ON p.id = v.patient_id
           LEFT JOIN samples s ON s.invoice_line_id = il.id
           ORDER BY il.id DESC"""
    )


def lab_tech_dashboard(staff):
    orders = lab_work_orders()
    awaiting_collection = [
        row for row in orders
        if row["sample_id"] is None and row["line_status"] != "Cancelled"
    ]
    awaiting_results = [
        row for row in orders
        if row["sample_status"] == "Collected" and row["result_id"] is None
    ]
    awaiting_verification = [
        row for row in orders if row["result_status"] == "Pending verification"
    ]
    reports_issued = db_one(
        """SELECT COUNT(*) AS n FROM report_versions
           WHERE authorized = 1 AND substr(issued_at, 1, 10) = ?""",
        (datetime.now().astimezone().date().isoformat(),),
    )["n"]
    st.title("Lab Tech Dashboard")
    st.caption(f"Laboratory work queue · Signed in as {staff['name']}")
    metrics = st.columns(4)
    metrics[0].metric("Awaiting collection", len(awaiting_collection))
    metrics[1].metric("Awaiting result entry", len(awaiting_results))
    metrics[2].metric("Awaiting verification", len(awaiting_verification))
    metrics[3].metric("Reports authorized today", reports_issued)
    st.button(
        "Open Lab Work",
        key="lab_dashboard_open_work",
        type="primary",
        on_click=go_to_page,
        args=("Lab Work",),
    )
    st.subheader("Active lab queue")
    active_orders = [
        {
            "Invoice": row["invoice_no"],
            "Patient": row["full_name"],
            "Patient ID": row["patient_code"],
            "Test": row["test_name"],
            "Department": row["department"],
            "Sample": row["sample_code"] or row["sample_status"],
            "Result": row["result_status"] or "Not entered",
        }
        for row in orders
        if row["result_status"] != "Verified" and row["line_status"] != "Cancelled"
    ]
    if active_orders:
        st.dataframe(active_orders, hide_index=True, use_container_width=True)
    else:
        st.success("No tests are waiting for lab processing.")


def lab_work_screen(staff):
    st.title("Lab Work")
    if staff["role"] not in ("Lab Tech", "Admin", "Owner"):
        st.error("Only Lab Tech, Admin, or Owner accounts can access lab work.")
        return

    orders = lab_work_orders()
    collect_tab, results_tab, verify_tab = st.tabs(
        ["Sample collection", "Result entry", "Verify & authorize"]
    )
    with collect_tab:
        queue = [
            row for row in orders
            if row["sample_id"] is None and row["line_status"] != "Cancelled"
        ]
        if not queue:
            st.success("No tests are awaiting sample collection.")
        else:
            st.dataframe(
                [
                    {
                        "Invoice": row["invoice_no"],
                        "Patient": row["full_name"],
                        "Patient ID": row["patient_code"],
                        "Test": row["test_name"],
                        "Department": row["department"],
                    }
                    for row in queue
                ],
                hide_index=True,
                use_container_width=True,
            )
            order_choices = {
                f"{row['invoice_no']} · {row['full_name']} · {row['test_name']} · {row['department']}": row
                for row in queue
            }
            selected_order = dropdown("Test for sample collection", list(order_choices))
            order = order_choices[selected_order]
            st.caption(
                f"Patient ID: {order['patient_code']} · "
                f"Age: {order['age_value']} {order['age_unit']} · Sex: {order['sex']}"
            )
            if st.button("Collect sample", type="primary", key="collect_lab_sample"):
                try:
                    with database() as connection:
                        sample_code = collect_lab_sample(
                            connection,
                            order["line_id"],
                            staff["id"],
                            order["invoice_no"],
                            order["test_name"],
                        )
                except ValueError as error:
                    st.error(str(error))
                    return
                st.success(f"Sample {sample_code} recorded.")
                st.rerun()

    with results_tab:
        queue = [
            row for row in orders
            if row["sample_status"] == "Collected" and row["result_id"] is None
        ]
        if not queue:
            st.success("No collected samples are awaiting result entry.")
        else:
            result_choices = {
                f"{row['invoice_no']} · {row['full_name']} · {row['test_name']} · {row['sample_code']}": row
                for row in queue
            }
            selected_result = dropdown("Collected sample for result entry", list(result_choices))
            order = result_choices[selected_result]
            st.caption(
                f"Patient ID: {order['patient_code']} · "
                f"Age: {order['age_value']} {order['age_unit']} · "
                f"Sex: {order['sex']} · Department: {order['department']}"
            )
            with st.form("lab_result_entry", clear_on_submit=True):
                result_summary = st.text_area(
                    "Result / observations *",
                    help="Enter the result text that should be reviewed before report authorization.",
                )
                submitted = st.form_submit_button("Save result for verification", type="primary")
            if submitted:
                if not result_summary.strip():
                    st.error("Enter the result or observations before submitting.")
                else:
                    with database() as connection:
                        cursor = connection.execute(
                            """INSERT INTO results(invoice_line_id, status, result_summary)
                               VALUES (?, 'Pending verification', ?)""",
                            (order["line_id"], result_summary.strip()),
                        )
                        audit(
                            connection,
                            staff["id"],
                            "Lab result entered",
                            "result",
                            cursor.lastrowid,
                            "",
                            f"invoice={order['invoice_no']}; test={order['test_name']}",
                        )
                    st.success("Result saved and added to the verification queue.")
                    st.rerun()

    with verify_tab:
        queue = [row for row in orders if row["result_status"] == "Pending verification"]
        if not queue:
            st.success("No results are awaiting verification.")
        else:
            verify_choices = {
                f"{row['invoice_no']} · {row['full_name']} · {row['test_name']} · {row['sample_code']}": row
                for row in queue
            }
            selected_result = dropdown("Result to verify", list(verify_choices))
            order = verify_choices[selected_result]
            st.caption(
                f"Patient ID: {order['patient_code']} · "
                f"Age: {order['age_value']} {order['age_unit']} · "
                f"Sex: {order['sex']} · Department: {order['department']}"
            )
            st.text_area(
                "Result for review",
                value=order["result_summary"] or "",
                disabled=True,
                key=f"lab_result_review_{order['result_id']}",
            )
            with st.form("lab_result_verification", clear_on_submit=True):
                confirmed = st.checkbox("I reviewed this result and confirm it is ready to issue.")
                submitted = st.form_submit_button("Verify & authorize report", type="primary")
            if submitted:
                if not confirmed:
                    st.error("Confirm the result review before authorizing a report.")
                else:
                    with database() as connection:
                        result_cursor = connection.execute(
                            """UPDATE results SET status = 'Verified', verified_by = ?, verified_at = ?
                               WHERE id = ? AND status = 'Pending verification'""",
                            (staff["name"], now(), order["result_id"]),
                        )
                        if result_cursor.rowcount != 1:
                            raise RuntimeError("The selected result changed before verification.")
                        version = connection.execute(
                            """SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                               FROM report_versions WHERE invoice_line_id = ?""",
                            (order["line_id"],),
                        ).fetchone()["next_version"]
                        report_cursor = connection.execute(
                            """INSERT INTO report_versions(invoice_line_id, result_id, version,
                                                           authorized, issued_by, issued_at)
                               VALUES (?, ?, ?, 1, ?, ?)""",
                            (order["line_id"], order["result_id"], version, staff["name"], now()),
                        )
                        connection.execute(
                            "UPDATE invoice_lines SET status = 'Completed' WHERE id = ?",
                            (order["line_id"],),
                        )
                        audit(
                            connection,
                            staff["id"],
                            "Result verified and report authorized",
                            "report",
                            report_cursor.lastrowid,
                            "Pending verification",
                            f"invoice={order['invoice_no']}; test={order['test_name']}; version={version}",
                        )
                    st.success(f"Result verified and report version {version} authorized.")
                    st.rerun()


def go_to_page(page):
    st.session_state["navigation_page"] = page


def visit_demographics(default_age=0, default_sex=None):
    age_cols = st.columns(3)
    with age_cols[0]:
        visit_age = st.number_input(
            "Age at this visit",
            min_value=0,
            max_value=120,
            value=default_age,
            key="new_invoice_visit_age",
        )
    with age_cols[1]:
        age_unit = dropdown(
            "Age unit",
            ("Years", "Months"),
            key="new_invoice_age_unit",
        )
    age_days = float(visit_age) * 365.2425
    age_days_text = ""
    if age_unit == "Months":
        with age_cols[2]:
            age_days_text = st.text_input(
                "Additional days *",
                placeholder="Enter 0–30 days",
                key="new_invoice_age_days",
            )
        if age_days_text.isdigit() and 0 <= int(age_days_text) <= 30:
            age_days = float(visit_age) * 30.4375 + int(age_days_text)
    visit_sex = dropdown(
        "Sex",
        ("Female", "Male", "Other"),
        key="new_invoice_sex",
        selected_option=default_sex if default_sex in ("Female", "Male", "Other") else None,
    )
    return visit_age, visit_sex, age_unit, age_days, age_days_text


def new_invoice(staff):
    st.title("New Invoice")
    if st.session_state.pop("new_invoice_reset_pending", False):
        for key in (
            "new_invoice_patient_mode",
            "new_invoice_patient_search",
            "new_invoice_selected_patient_id",
            "new_invoice_patient_name",
            "new_invoice_patient_phone",
            "new_invoice_patient_address",
            "new_invoice_visit_age",
            "new_invoice_age_unit",
            "new_invoice_age_days",
            "new_invoice_sex",
            "new_invoice_tests",
            "new_invoice_ordered_by",
            "new_invoice_referrer",
            "new_invoice_discount",
            "new_invoice_paid",
            "new_invoice_payment_method",
            "new_invoice_payment_reference",
        ):
            st.session_state.pop(key, None)
    patients = db_rows(
        "SELECT id, patient_code, full_name, phone, sex, age, address FROM patients ORDER BY full_name"
    )
    patient_mode = st.radio(
        "Patient",
        ("Find existing", "Register new"),
        horizontal=True,
        key="new_invoice_patient_mode",
    )
    selected_patient = None
    if patient_mode == "Find existing":
        if not patients:
            st.info("No patients are registered yet. Select “Register new” to create the first patient.")
        else:
            patient_map = {
                f"{patient['patient_code']} · {patient['full_name']} · {patient['phone']}": patient
                for patient in patients
            }
            choice = dropdown(
                "Find patient by ID, name or contact",
                list(patient_map),
                key="new_invoice_patient_search",
                allow_empty=True,
            )
            selected_patient = patient_map.get(choice) if choice else None
            if selected_patient:
                if (
                    st.session_state.get("new_invoice_selected_patient_id")
                    != selected_patient["id"]
                ):
                    st.session_state["new_invoice_selected_patient_id"] = selected_patient["id"]
                    st.session_state["new_invoice_visit_age"] = (
                        int(selected_patient["age"] or 0)
                    )
                    st.session_state["new_invoice_sex"] = (
                        selected_patient["sex"]
                        if selected_patient["sex"] in ("Female", "Male", "Other")
                        else None
                    )
                st.success(
                    f"Selected: {selected_patient['patient_code']} · "
                    f"{selected_patient['full_name']} · {selected_patient['phone']}"
                )
            else:
                st.session_state.pop("new_invoice_selected_patient_id", None)
        visit_age, visit_sex, age_unit, age_days, age_days_text = visit_demographics(
            default_age=int(selected_patient["age"] or 0) if selected_patient else 0,
            default_sex=selected_patient["sex"] if selected_patient else None,
        )
    else:
        patient_cols = st.columns(2)
        with patient_cols[0]:
            patient_name = st.text_input("Patient name *", key="new_invoice_patient_name")
        with patient_cols[1]:
            patient_phone = st.text_input(
                "Contact number *",
                key="new_invoice_patient_phone",
            )
        visit_age, visit_sex, age_unit, age_days, age_days_text = visit_demographics()
        patient_address = st.text_input(
            "Address (at least one word) *",
            key="new_invoice_patient_address",
        )
        if patient_name.strip() or patient_phone.strip():
            duplicate_term = f"%{patient_name.strip()}%"
            possible_duplicates = db_rows(
                """SELECT patient_code, full_name, phone, address FROM patients
                   WHERE (? <> '' AND phone = ?) OR (? <> '' AND full_name LIKE ?)
                   ORDER BY id DESC LIMIT 5""",
                (patient_phone.strip(), patient_phone.strip(), patient_name.strip(), duplicate_term),
            )
            if possible_duplicates:
                st.warning("Possible existing patient found. Review before creating a new patient number.")
                st.dataframe(possible_duplicates, hide_index=True, use_container_width=True)

    tests = db_rows("SELECT * FROM tests WHERE active = 1 ORDER BY department, name")
    if not tests:
        st.warning("No active tests are configured. Add tests in Accounts & Referrers.")
        return
    test_map = {
        f"{test['name']} · {test['department']} · {money(test['price'])} · {test['code']}": test
        for test in tests
    }
    test_labels = dropdown("Tests *", list(test_map), multi=True, key="new_invoice_tests")
    selected_tests = [test_map[label] for label in test_labels]
    line_discounts = {}
    master_enabled = st.session_state.get("new_invoice_master_discount_enabled", False)
    if selected_tests:
        st.caption("Selected tests")
        if master_enabled:
            st.caption("Individual discounts are inactive while Master Discount is applied; their settings are preserved.")
        for index, (label, test) in enumerate(zip(test_labels, selected_tests)):
            details, mrp, discount_controls, net_column, remove_button = st.columns(
                [4.5, 1.0, 3.0, 1.0, 0.9],
                gap="medium",
            )
            with details:
                st.write(
                    f"**{test['name']}** · {test['department']} · "
                    f"{money(test['price'])} · {test['code']}"
                )
            discount_key = f"new_invoice_line_discount_{test['id']}"
            enabled_key = f"{discount_key}_enabled"
            test_discounts = st.session_state.setdefault("new_invoice_test_discounts", {})
            test_discount = test_discounts.setdefault(
                str(test["id"]),
                {"enabled": False, "type": "Percentage", "value": 50.0},
            )
            if enabled_key not in st.session_state:
                st.session_state[enabled_key] = bool(test_discount.get("enabled", False))
            if f"{discount_key}_type" not in st.session_state:
                st.session_state[f"{discount_key}_type"] = test_discount.get("type", "Percentage")
            enabled = bool(
                st.session_state.get(enabled_key, test_discount.get("enabled", False))
            )
            discount_kind = st.session_state.get(
                f"{discount_key}_type",
                test_discount.get("type", "Percentage"),
            )
            percent_key = f"{discount_key}_percent_value"
            amount_key = f"{discount_key}_amount_value"
            if percent_key in st.session_state:
                st.session_state[percent_key] = min(
                    50.0,
                    max(0.0, float(st.session_state[percent_key])),
                )
            if amount_key in st.session_state:
                st.session_state[amount_key] = min(
                    float(test["price"]),
                    max(0.0, float(st.session_state[amount_key])),
                )
            with mrp:
                st.markdown(
                    f"<div style='height:28px'></div><span style='text-decoration:line-through'>{money(test['price'])}</span>",
                    unsafe_allow_html=True,
                )
            with discount_controls:
                value_column, percent_column, amount_column = st.columns([1.7, 0.55, 0.55])
                if enabled:
                    if discount_kind == "Percentage":
                        with value_column:
                            value = st.number_input(
                                "Per-test discount",
                                min_value=0.0,
                                max_value=50.0,
                                value=min(
                                    50.0,
                                    max(
                                        0.0,
                                        float(
                                            st.session_state.get(
                                                percent_key,
                                                test_discount.get("value", 50.0)
                                                if discount_kind == "Percentage"
                                                else 50.0,
                                            )
                                        ),
                                    ),
                                ),
                                step=1.0,
                                key=percent_key,
                                disabled=master_enabled,
                                label_visibility="collapsed",
                            )
                    else:
                        with value_column:
                            value = st.number_input(
                                "Per-test discount",
                                min_value=0.0,
                                max_value=float(test["price"]),
                                value=min(
                                    float(test["price"]),
                                    max(
                                        0.0,
                                        float(
                                            st.session_state.get(
                                                amount_key,
                                                test_discount.get("value", 0.0)
                                                if discount_kind == "Amount"
                                                else 0.0,
                                            )
                                        ),
                                    ),
                                ),
                                step=10.0,
                                key=amount_key,
                                disabled=master_enabled,
                                label_visibility="collapsed",
                            )
                else:
                    discount_kind = ""
                    value = 0.0
                    with value_column:
                        st.number_input(
                            "Per-test discount",
                            min_value=0.0,
                            max_value=50.0,
                            value=0.0,
                            step=1.0,
                            disabled=True,
                            label_visibility="collapsed",
                            key=f"{discount_key}_inactive",
                        )
                with percent_column:
                    if st.button(
                        "%",
                        key=f"{discount_key}_percent_button",
                        disabled=master_enabled,
                        type="primary" if enabled and discount_kind == "Percentage" else "secondary",
                    ):
                        set_invoice_line_discount_type(test["id"], "Percentage")
                with amount_column:
                    if st.button(
                        "৳",
                        key=f"{discount_key}_amount_button",
                        disabled=master_enabled,
                        type="primary" if enabled and discount_kind == "Amount" else "secondary",
                    ):
                        set_invoice_line_discount_type(test["id"], "Amount")
            if enabled and discount_kind == "Percentage":
                line_amount = min(
                    float(test["price"]) * float(value) / 100.0,
                    float(test["price"]) * 0.50,
                )
                if value > 50:
                    line_amount = float(test["price"]) * 0.50
            elif enabled and discount_kind == "Amount":
                line_amount = min(float(test["price"]), float(value))
            else:
                line_amount = 0.0
            test_discounts[str(test["id"])] = {
                "enabled": enabled,
                "type": discount_kind or "Percentage",
                "value": float(value),
            }
            with net_column:
                st.markdown(
                    f"<div style='height:28px'></div><b>{money(max(0.0, float(test['price']) - line_amount))}</b>",
                    unsafe_allow_html=True,
                )
            with remove_button:
                st.button(
                    "🗑",
                    key=f"remove_invoice_test_{index}",
                    on_click=remove_invoice_test,
                    args=(label,),
                    help="Remove test",
                    type="primary",
                )
            line_discounts[test["id"]] = {
                "type": discount_kind,
                "value": float(value),
            }
    st.caption("Type to filter, then press Enter, Tab, or click to add a test.")
    gross = sum(float(test["price"]) for test in selected_tests)
    individual_discount = sum(
        (
            min(float(test["price"]) * 0.50, float(test["price"]) * line_discounts[test["id"]]["value"] / 100.0)
            if line_discounts[test["id"]]["type"] == "Percentage"
            else min(float(test["price"]), line_discounts[test["id"]]["value"])
        )
        for test in selected_tests
    )
    st.caption(f"Test subtotal: **{money(gross)}**")
    referrers = db_rows("SELECT * FROM referrers WHERE active = 1 ORDER BY name")
    referrer_map = {"No referrer": None}
    referrer_map.update(
        {f"{r['name']} · {r['referrer_type']}": r for r in referrers}
    )
    add_referrer_option = "＋ Add new referrer"
    ordered_referrer_map = dict(referrer_map)
    ordered_referrer_map[add_referrer_option] = None
    preferred_ordered_referrer = st.session_state.pop(
        "new_invoice_ordered_by_referrer_option", None
    )
    ordered_by_name = dropdown(
        "Tests ordered by",
        list(ordered_referrer_map),
        selected_option=preferred_ordered_referrer,
        key="new_invoice_ordered_by",
    )
    if ordered_by_name == add_referrer_option:
        with st.form("invoice_new_ordered_by_referrer", clear_on_submit=True):
            st.subheader("Add a referrer for Tests ordered by")
            ordered_new_name = st.text_input("Doctor / third-party name *", key="ordered_new_referrer_name")
            ordered_new_type = st.radio(
                "Referrer type",
                ("Doctor", "3rd party"),
                horizontal=True,
                key="ordered_new_referrer_type",
            )
            ordered_new_phone = st.text_input(
                "Referrer contact number", key="ordered_new_referrer_phone"
            )
            ordered_new_commission_type = "Percentage"
            ordered_new_commission = 0.0
            ordered_new_commission_amount = 0.0
            if staff["role"] == "Owner":
                ordered_new_commission_type = st.radio(
                    "Commission calculation",
                    COMMISSION_TYPES,
                    horizontal=True,
                    key="ordered_new_referrer_commission_type",
                )
                ordered_new_commission = st.number_input(
                    "Default commission rate (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.5,
                    key="ordered_new_referrer_commission",
                )
                ordered_new_commission_amount = st.number_input(
                    "Default commission amount per invoice (৳)",
                    min_value=0.0,
                    value=0.0,
                    step=50.0,
                    key="ordered_new_referrer_commission_amount",
                )
            else:
                st.caption("An Owner can set this referrer's commission in Accounts & Referrers.")
            ordered_referrer_submitted = st.form_submit_button("Save referrer", type="primary")
        if ordered_referrer_submitted:
            if not ordered_new_name.strip():
                st.error("Enter the doctor or third-party name.")
            elif db_one(
                "SELECT id FROM referrers WHERE lower(name) = lower(?)",
                (ordered_new_name.strip(),),
            ):
                st.error("A referrer with that name already exists.")
            else:
                try:
                    with database() as connection:
                        connection.execute(
                            """INSERT INTO referrers(name, referrer_type, phone, commission_percent,
                                                     commission_type, commission_amount)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                ordered_new_name.strip(),
                                ordered_new_type,
                                ordered_new_phone.strip(),
                                ordered_new_commission,
                                ordered_new_commission_type,
                                ordered_new_commission_amount,
                            ),
                        )
                        audit(
                            connection,
                            staff["id"],
                            "Referrer added",
                            "referrer",
                            ordered_new_name.strip(),
                            "",
                            f"type={ordered_new_type}; active; source=Tests ordered by",
                        )
                    st.session_state["new_invoice_ordered_by_referrer_option"] = (
                        f"{ordered_new_name.strip()} · {ordered_new_type}"
                    )
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That referrer could not be saved because its name is already in use.")
    referrer_map[add_referrer_option] = None
    preferred_referrer = st.session_state.pop("new_invoice_referrer_option", None)
    referrer_name = dropdown(
        "Patient referred by",
        list(referrer_map),
        selected_option=preferred_referrer,
        key="new_invoice_referrer",
    )
    if referrer_name == add_referrer_option:
        with st.form("invoice_new_referrer", clear_on_submit=True):
            st.subheader("Add a referrer")
            new_referrer_name = st.text_input("Doctor / third-party name *")
            new_referrer_type = st.radio(
                "Referrer type",
                ("Doctor", "3rd party"),
                horizontal=True,
            )
            new_referrer_phone = st.text_input("Referrer contact number")
            new_referrer_commission = 0.0
            new_referrer_commission_amount = 0.0
            new_referrer_commission_type = "Percentage"
            if staff["role"] == "Owner":
                new_referrer_commission_type = st.radio(
                    "Commission calculation",
                    COMMISSION_TYPES,
                    horizontal=True,
                    help="Percentage is calculated from test subtotal; fixed amount is paid per invoice.",
                )
                new_referrer_commission = st.number_input(
                    "Default commission rate (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.5,
                    help="Used when Percentage is selected.",
                )
                new_referrer_commission_amount = st.number_input(
                    "Default commission amount per invoice (৳)",
                    min_value=0.0,
                    value=0.0,
                    step=50.0,
                    help="Used when Fixed amount is selected.",
                )
            else:
                st.caption("An Owner can set this referrer's commission in Accounts & Referrers.")
            add_referrer_submitted = st.form_submit_button("Save referrer", type="primary")
        if add_referrer_submitted:
            if not new_referrer_name.strip():
                st.error("Enter the doctor or third-party name.")
            elif db_one(
                "SELECT id FROM referrers WHERE lower(name) = lower(?)",
                (new_referrer_name.strip(),),
            ):
                st.error("A referrer with that name already exists.")
            else:
                try:
                    with database() as connection:
                        connection.execute(
                            """INSERT INTO referrers(name, referrer_type, phone, commission_percent,
                                                     commission_type, commission_amount)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                new_referrer_name.strip(),
                                new_referrer_type,
                                new_referrer_phone.strip(),
                                new_referrer_commission,
                                new_referrer_commission_type,
                                new_referrer_commission_amount,
                            ),
                        )
                        audit(
                            connection,
                            staff["id"],
                            "Referrer added",
                            "referrer",
                            new_referrer_name.strip(),
                            "",
                            f"type={new_referrer_type}; active",
                        )
                    st.session_state["new_invoice_referrer_option"] = (
                        f"{new_referrer_name.strip()} · {new_referrer_type}"
                    )
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("That referrer could not be saved because its name is already in use.")
    referral = referrer_map[referrer_name]
    if referral and staff["role"] == "Owner":
        st.caption(
            f"Saved default commission: {commission_description(referral)} "
            "— applied automatically to this invoice."
        )
    ordered_by = referrer_map[ordered_by_name]
    master_enabled = st.checkbox("Apply Master Discount", key="new_invoice_master_discount_enabled")
    master_discount_type = st.session_state.get("new_invoice_master_discount_type", "Percentage")
    master_discount_value = 0.0
    if master_enabled:
        st.caption("Master Discount")
        value_column, percent_column, amount_column = st.columns([4.0, 0.55, 0.55])
        with percent_column:
            if st.button(
                "%",
                key="new_invoice_master_discount_percent_button",
                type="primary" if master_discount_type == "Percentage" else "secondary",
            ):
                st.session_state["new_invoice_master_discount_type"] = "Percentage"
                master_discount_type = "Percentage"
        with amount_column:
            if st.button(
                "৳",
                key="new_invoice_master_discount_amount_button",
                type="primary" if master_discount_type == "Amount" else "secondary",
            ):
                st.session_state["new_invoice_master_discount_type"] = "Amount"
                master_discount_type = "Amount"
        with value_column:
            if master_discount_type == "Percentage":
                master_discount_value = st.number_input(
                    "Master Discount %",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.get("new_invoice_master_discount_value_percent", 50.0)),
                    step=1.0,
                    key="new_invoice_master_discount_value_percent",
                    label_visibility="collapsed",
                )
                discount = round(min(gross, gross * master_discount_value / 100.0), 2)
            else:
                master_discount_value = st.number_input(
                    "Master Discount amount",
                    min_value=0.0,
                    max_value=float(gross),
                    value=float(st.session_state.get("new_invoice_master_discount_value_amount", 0.0)),
                    step=50.0,
                    key="new_invoice_master_discount_value_amount",
                    label_visibility="collapsed",
                )
                discount = round(min(gross, master_discount_value), 2)
    else:
        master_discount_type = ""
        master_discount_value = 0.0
        discount = round(individual_discount, 2)
    net = max(0, gross - discount)
    st.markdown(f"**Net payable: {money(net)}**")
    session = current_session()
    if session:
        st.caption(f"Payment will be posted to the open shift (opened {session['opened_at']}).")
    else:
        st.warning("An invoice can be saved without payment. Open the day before taking payment.")
    paid = st.number_input(
        "Receive now (৳)",
        min_value=0.0,
        max_value=float(net),
        value=0.0,
        step=100.0,
        key="new_invoice_paid",
    )
    payment_method = dropdown(
        "Payment method",
        PAYMENT_METHODS,
        key="new_invoice_payment_method",
    )
    payment_reference = st.text_input(
        "Transaction number (required for mobile/bank payments)",
        key="new_invoice_payment_reference",
    )
    if st.button("Create invoice", type="primary", disabled=not selected_tests):
        if patient_mode == "Find existing" and not selected_patient:
            st.error("Select an existing patient or register a new one.")
            return
        if patient_mode == "Register new" and (not patient_name.strip() or not patient_phone.strip()):
            st.error("Patient name and contact number are required.")
            return
        if patient_mode == "Register new" and not patient_address.strip().split():
            st.error("Enter at least one word of address.")
            return
        if age_unit == "Months" and (not age_days_text.isdigit() or not 0 <= int(age_days_text) <= 30):
            st.error("Enter the patient's age in days (0–30) when using months.")
            return
        if paid > 0 and not session:
            st.error("Open a cashier shift before recording a payment.")
            return
        if paid > 0 and payment_method in REFERENCE_REQUIRED_METHODS and not payment_reference.strip():
            st.error(f"Enter a transaction number for {payment_method} payments.")
            return
        try:
            with database() as connection:
                connection.execute("BEGIN IMMEDIATE")
                created_at = now()
                if patient_mode == "Register new":
                    cursor = connection.execute(
                        """INSERT INTO patients(patient_code, full_name, sex, age, phone, address, created_at)
                           VALUES ('PENDING', ?, ?, ?, ?, ?, ?)""",
                        (patient_name.strip(), visit_sex, int(visit_age), patient_phone.strip(), patient_address.strip(), created_at),
                    )
                    patient_id = cursor.lastrowid
                    patient_code = f"SDP-{patient_id:06d}"
                    connection.execute("UPDATE patients SET patient_code = ? WHERE id = ?", (patient_code, patient_id))
                else:
                    patient_id = selected_patient["id"]
                visit_cursor = connection.execute(
                    """INSERT INTO visits(patient_id, visit_no, age_value, age_unit, age_days, sex, created_at, created_by)
                       VALUES (?, 'PENDING', ?, ?, ?, ?, ?, ?)""",
                    (patient_id, visit_age, age_unit.lower(), age_days, visit_sex, created_at, staff["id"]),
                )
                visit_id = visit_cursor.lastrowid
                visit_no = f"VIS-{datetime.now():%y%m%d}-{visit_id:05d}"
                connection.execute("UPDATE visits SET visit_no = ? WHERE id = ?", (visit_no, visit_id))
                bill_counter = connection.execute(
                    "SELECT current_value FROM billing_sequences WHERE name = 'bill'"
                ).fetchone()["current_value"] + 1
                connection.execute(
                    "UPDATE billing_sequences SET current_value = ? WHERE name = 'bill'",
                    (bill_counter,),
                )
                invoice_no = f"SD-{bill_counter:06d}"
                invoice_cursor = connection.execute(
                    """INSERT INTO invoices(visit_id, invoice_no, referrer_id, ordered_by_referrer_id,
                                             gross, master_discount_type, master_discount_value,
                                             discount, net, paid, due, status, created_at, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'Confirmed', ?, ?)""",
                    (visit_id, invoice_no, referral["id"] if referral else None,
                     ordered_by["id"] if ordered_by else None, gross,
                     master_discount_type if master_enabled else "", master_discount_value,
                     discount, net, net, created_at, staff["id"]),
                )
                invoice_id = invoice_cursor.lastrowid
                for test in selected_tests:
                    line_discount = line_discounts[test["id"]]
                    line_discount_amount = (
                        round(min(float(test["price"]) * line_discount["value"] / 100.0, float(test["price"]) * 0.50), 2)
                        if line_discount["type"] == "Percentage"
                        else round(min(float(test["price"]), line_discount["value"]), 2)
                    )
                    connection.execute(
                        """INSERT INTO invoice_lines(
                               invoice_id, test_id, test_name, department, unit_price,
                               discount_type, discount_value, discount_amount,
                               assigned_to, assigned_at
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            invoice_id, test["id"], test["name"], test["department"], test["price"],
                            line_discount["type"], line_discount["value"], line_discount_amount,
                            test["department"], created_at,
                        ),
                    )
                if gross > 0:
                    bill_lines = [
                        {
                            "account_key": "test_revenue",
                            "credit": gross,
                            "description": f"Test charges · {invoice_no}",
                        }
                    ]
                    if net > 0:
                        bill_lines.append(
                            {
                                "account_key": "accounts_receivable",
                                "debit": net,
                                "description": f"Patient balance · {invoice_no}",
                            }
                        )
                    if discount > 0:
                        bill_lines.append(
                            {
                                "account_key": "discount_expense",
                                "debit": discount,
                                "description": f"Discount · {invoice_no}",
                            }
                        )
                    post_journal_entry(
                        connection,
                        created_at[:10],
                        f"Bill confirmed · {invoice_no}",
                        bill_lines,
                        created_by=staff["id"],
                        source_type="Invoice",
                        source_key=f"invoice:{invoice_id}",
                        source_id=invoice_id,
                    )
                if referral:
                    commission = calculate_commission(gross, referral)
                    connection.execute(
                        """INSERT INTO commission_entries(invoice_id, referrer_id, amount, created_at)
                           VALUES (?, ?, ?, ?)""",
                        (invoice_id, referral["id"], commission, created_at),
                    )
                    if commission > 0:
                        post_journal_entry(
                            connection,
                            created_at[:10],
                            f"Referral commission accrued · {invoice_no}",
                            [
                                {
                                    "account_key": "commission_expense",
                                    "debit": commission,
                                    "party_type": "Referrer",
                                    "party_id": referral["id"],
                                    "description": referral["name"],
                                },
                                {
                                    "account_key": "referrer_payable",
                                    "credit": commission,
                                    "party_type": "Referrer",
                                    "party_id": referral["id"],
                                    "description": referral["name"],
                                },
                            ],
                            created_by=staff["id"],
                            source_type="Commission accrued",
                            source_key=f"commission:{invoice_id}",
                            source_id=invoice_id,
                        )
                audit(
                    connection,
                    staff["id"],
                    "Bill confirmed",
                    "bill",
                    invoice_no,
                    "",
                    f"visit={visit_no}; patient={patient_id}; gross={gross:.2f}; discount={discount:.2f}; net={net:.2f}",
                )
                if paid > 0:
                    new_invoice_row = dict(connection.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())
                    add_payment(connection, new_invoice_row, paid, payment_method, payment_reference.strip(), staff["id"], session["id"])
            st.success(f"Bill {invoice_no} confirmed for visit {visit_no}. Tests are routed by department; sample IDs are created at collection.")
            st.session_state["last_invoice"] = invoice_no
            st.session_state["new_invoice_reset_pending"] = True
            st.rerun()
        except ValueError as error:
            st.error(str(error))
        except sqlite3.IntegrityError as error:
            st.error(f"Invoice could not be saved because a linked record was invalid: {error}")
    if st.session_state.get("last_invoice"):
        st.info(f"Last created invoice: {st.session_state['last_invoice']}")


def invoice_search(staff):
    st.title("Invoices")
    search = st.text_input("Find by invoice number, patient ID, name or contact")
    query = """SELECT i.id, i.invoice_no, p.patient_code, p.full_name, p.phone, rr.name AS referred_by, i.gross, i.discount,
                      i.net, i.paid, i.due, i.refund_due,
                      COALESCE((SELECT SUM(rf.amount) FROM refunds rf WHERE rf.invoice_id = i.id), 0) AS refunded,
                      i.status AS bill_status,
                      CASE WHEN i.refund_due > 0.005
                                 AND EXISTS (SELECT 1 FROM refunds rf WHERE rf.invoice_id = i.id)
                                THEN 'Partially refunded; balance due'
                           WHEN i.refund_due > 0.005 THEN 'Patient refund due'
                           WHEN EXISTS (SELECT 1 FROM refunds rf WHERE rf.invoice_id = i.id)
                                THEN 'Refunded'
                           WHEN i.due <= 0.005 THEN 'Paid'
                           WHEN i.paid > 0 THEN 'Partly paid' ELSE 'Unpaid' END AS payment_status,
                      i.created_at
               FROM invoices i JOIN visits v ON v.id = i.visit_id
               JOIN patients p ON p.id = v.patient_id
               LEFT JOIN referrers rr ON rr.id = i.referrer_id"""
    params = ()
    if search.strip():
        term = f"%{search.strip()}%"
        query += """ WHERE i.invoice_no LIKE ? OR p.patient_code LIKE ? OR p.full_name LIKE ? OR p.phone LIKE ?
                     OR EXISTS (SELECT 1 FROM invoice_lines il WHERE il.invoice_id = i.id AND il.test_name LIKE ?)
                     OR EXISTS (SELECT 1 FROM referrers r WHERE (r.id = i.referrer_id OR r.id = i.ordered_by_referrer_id) AND r.name LIKE ?)"""
        params = (term, term, term, term, term, term)
    query += " ORDER BY i.id DESC LIMIT 100"
    invoices = db_rows(query, params)
    if invoices:
        options = {
            f"{row['invoice_no']} · {row['full_name']} · Due {money(row['due'])}": row for row in invoices
        }
        selected = dropdown("Select invoice to view / reprint", list(options))
        invoice = options[selected]
        lines = db_rows(
            """SELECT test_name, department, unit_price, status, assigned_to,
                      cancellation_reason, cancelled_at
               FROM invoice_lines WHERE invoice_id = ? ORDER BY id""",
            (invoice["id"],),
        )
        payments = db_rows(
            "SELECT id, amount, method, reference, received_at FROM payments WHERE invoice_id = ? ORDER BY id",
            (invoice["id"],),
        )
        st.subheader(f"Receipt · {invoice['invoice_no']}")
        st.write(f"**Patient:** {invoice['full_name']} · {invoice['patient_code']} · {invoice['phone']}")
        st.write(
            f"**Date:** {invoice['created_at']} · **Bill:** {invoice['bill_status']} · "
            f"**Payment:** {invoice['payment_status']}"
        )
        st.dataframe(lines, hide_index=True, use_container_width=True)
        a, b, c, d, e, f = st.columns(6)
        money_metric(a, "Subtotal", invoice["gross"])
        money_metric(b, "Discount", invoice["discount"])
        money_metric(c, "Total received", invoice["paid"])
        money_metric(d, "Refunded", invoice["refunded"])
        money_metric(e, "Due", invoice["due"])
        money_metric(f, "Refund due", invoice["refund_due"])
        if invoice["refund_due"] > 0:
            st.warning(
                "The canceled test reduced the bill below the amount already collected. "
                "This amount remains recorded as patient credit / refund due; payment history is unchanged."
            )
        if payments:
            st.caption("Payment history")
            st.dataframe(payments, hide_index=True, use_container_width=True)
        if st.button("Prepare duplicate reprint"):
            with database() as connection:
                audit(connection, staff["id"], "Bill reprinted", "bill", invoice["invoice_no"], "", "Duplicate copy")
            st.session_state["reprint_invoice_id"] = invoice["id"]
        if st.session_state.get("reprint_invoice_id") == invoice["id"]:
            receipt_tests = "".join(
                f"<tr><td>{escape(line['test_name'])}</td><td>{escape(line['department'])}</td>"
                f"<td>{money(line['unit_price'])}</td><td>{escape(line['status'])}</td></tr>"
                for line in lines
            )
            patient_copy = f"""
                <h3>{APP_NAME} · Patient copy</h3><p><b>Duplicate</b> · {escape(invoice['invoice_no'])} · {escape(invoice['created_at'])}</p>
                <p>{escape(invoice['full_name'])} ({escape(invoice['patient_code'])}) · {escape(invoice['phone'])}</p>
                <table><thead><tr><th>Test</th><th>Department</th><th>Price</th><th>Status</th></tr></thead><tbody>{receipt_tests}</tbody></table>
                <p>Subtotal {money(invoice['gross'])} · Discount {money(invoice['discount'])}</p>
                <p>Net {money(invoice['net'])} · Received {money(invoice['paid'])} · Refunded {money(invoice['refunded'])} · Remaining due {money(invoice['due'])} · Refund due {money(invoice['refund_due'])}</p>
                <p>Please keep this bill for report collection.</p>
            """
            office_copy = patient_copy.replace("Patient copy", "Office copy").replace(
                "<h3>", '<h3 class="office-watermark">'
            )
            copies = f'<div class="copies"><section>{patient_copy}</section><section>{office_copy}</section></div>'
            owner_copy = ""
            if staff["role"] == "Owner":
                commission = db_one(
                    "SELECT amount FROM commission_entries WHERE invoice_id = ?", (invoice["id"],)
                )
                owner_copy = (
                    f"<section class='owner-copy'><h3>Owner copy · {escape(invoice['invoice_no'])}</h3>"
                    f"<p>Referrer: {escape(invoice['referred_by'] or '—')}</p>"
                    f"<p>Referrer commission: {money(commission['amount'] if commission else 0)}</p></section>"
                )
            printable = f"""<!doctype html><html><head><meta charset="utf-8"><title>{escape(invoice['invoice_no'])} Duplicate</title>
                <style>body{{font:14px Arial,sans-serif;color:#142238}}table{{width:100%;border-collapse:collapse}}
                th,td{{border-bottom:1px solid #ccd5e2;padding:6px;text-align:left}}.copies{{display:flex;gap:16px}}
                .copies section{{width:50%;border:1px solid #9aa8bb;padding:14px;position:relative}}
                .office-watermark:after{{content:'OFFICE COPY';position:absolute;right:10px;top:8px;color:#8794a5}}
                .owner-copy{{margin-top:20px;border:1px dashed #8290a4;padding:14px}}
                @media print{{button{{display:none}}}}</style></head><body>
                <p>Printed as Duplicate · {escape(now())}</p>{copies}{owner_copy}
                <script>window.print()</script></body></html>"""
            st.download_button(
                "Download printable duplicate",
                printable,
                file_name=f"{invoice['invoice_no']}-duplicate.html",
                mime="text/html",
            )
        if payments:
            payment_choices = {
                f"Payment #{item['id']} · {money(item['amount'])} · {item['method']} · {item['received_at']}": item
                for item in payments
            }
            chosen_payment = dropdown("Payment receipt", list(payment_choices))
            payment = payment_choices[chosen_payment]
            payment_receipt = (
                f"{APP_NAME} · Payment receipt\nReceipt: PAY-{payment['id']:07d}\n"
                f"Invoice: {invoice['invoice_no']}\nPatient: {invoice['full_name']} ({invoice['patient_code']})\n"
                f"Amount: {money(payment['amount'])}\nMethod: {payment['method']}\n"
                f"Reference: {payment['reference'] or '—'}\nReceived: {payment['received_at']}\n"
            )
            st.download_button(
                "Download payment receipt",
                payment_receipt,
                file_name=f"PAY-{payment['id']:07d}.txt",
                mime="text/plain",
            )
    else:
        st.caption("No matching invoices.")


def dues_screen(staff):
    st.title("Dues & Payments")
    total_credit_due = db_one(
        "SELECT COALESCE(SUM(refund_due), 0) AS total FROM invoices WHERE refund_due > 0"
    )["total"]
    total_cancellation_income = db_one(
        "SELECT COALESCE(SUM(retained_amount), 0) AS total FROM refunds"
    )["total"]
    invoices = db_rows(
        """SELECT i.id, i.invoice_no, p.full_name, p.patient_code, p.phone, i.net, i.paid, i.due
           FROM invoices i JOIN visits v ON v.id = i.visit_id JOIN patients p ON p.id = v.patient_id
           WHERE i.due > 0 ORDER BY i.created_at"""
    )
    balance_metrics = st.columns(3)
    money_metric(balance_metrics[0], "Total outstanding", sum(row["due"] for row in invoices))
    money_metric(balance_metrics[1], "Patient credit / refund due", total_credit_due)
    money_metric(balance_metrics[2], "Cancellation income retained", total_cancellation_income)
    if total_credit_due > 0:
        st.info(
            "Use the Patient refunds tab to record payouts. Refunds are entered in the shift ledger "
            "and reduce the patient's outstanding refund balance."
        )
    due_tab, refund_tab = st.tabs(["Collect patient due", "Patient refunds"])
    with due_tab:
        if not invoices:
            st.success("There are no outstanding patient invoices.")
        else:
            st.dataframe(invoices, hide_index=True, use_container_width=True)
            options = {
                f"{item['invoice_no']} · {item['full_name']} · Due {money(item['due'])}": item
                for item in invoices
            }
            selected = dropdown("Invoice to receive payment", list(options))
            invoice = options[selected]
            session = current_session()
            if not session:
                st.warning("Open a cashier day before receiving a payment.")
            else:
                with st.form(f"due_payment_{invoice['id']}", clear_on_submit=True):
                    amount = st.number_input(
                        "Amount received (৳)",
                        min_value=0.01,
                        max_value=float(invoice["due"]),
                        value=min(100.0, float(invoice["due"])),
                        step=50.0,
                    )
                    method = dropdown("Payment method", PAYMENT_METHODS)
                    reference = st.text_input("Transaction / payment reference")
                    submitted = st.form_submit_button("Record payment", type="primary")
                if submitted:
                    try:
                        with database() as connection:
                            add_payment(
                                connection,
                                invoice,
                                amount,
                                method,
                                reference.strip(),
                                staff["id"],
                                session["id"],
                            )
                    except ValueError as error:
                        st.error(str(error))
                    except sqlite3.IntegrityError:
                        st.error("This transaction number has already been used.")
                    else:
                        st.success(
                            f"Payment of {money(amount)} recorded against {invoice['invoice_no']}."
                        )
                        st.rerun()

    with refund_tab:
        refund_invoices = db_rows(
            """SELECT i.id, i.invoice_no, p.full_name, p.patient_code, p.phone,
                      i.net, i.paid, i.refund_due
               FROM invoices i JOIN visits v ON v.id = i.visit_id
               JOIN patients p ON p.id = v.patient_id
               WHERE i.refund_due > 0.005
               ORDER BY i.created_at, i.id"""
        )
        if refund_invoices:
            st.subheader("Patients owed a refund")
            st.dataframe(
                [
                    {
                        "Invoice": item["invoice_no"],
                        "Patient": item["full_name"],
                        "Patient ID": item["patient_code"],
                        "Contact": item["phone"],
                        "Revised bill": money(item["net"]),
                        "Previously paid": money(item["paid"]),
                        "Refund due": money(item["refund_due"]),
                    }
                    for item in refund_invoices
                ],
                hide_index=True,
                use_container_width=True,
            )
            refund_options = {
                f"{item['invoice_no']} · {item['full_name']} · {item['patient_code']} · Refund {money(item['refund_due'])}": item
                for item in refund_invoices
            }
            selected_refund = dropdown("Patient refund to issue", list(refund_options))
            invoice = refund_options[selected_refund]
            session = current_session()
            if not session:
                st.warning("Open a cashier day before issuing a patient refund.")
            else:
                with st.form(f"patient_refund_{invoice['id']}", clear_on_submit=True):
                    refund_amount = st.number_input(
                        "Refund amount (৳)",
                        min_value=0.01,
                        max_value=float(invoice["refund_due"]),
                        value=float(invoice["refund_due"]),
                        step=50.0,
                    )
                    refund_method = dropdown("Refund method", PAYMENT_METHODS)
                    refund_reference = st.text_input(
                        "Transaction / voucher reference",
                        help="Required for mobile wallet or bank refunds.",
                    )
                    refund_reason = st.text_input(
                        "Refund reason / authorization *",
                        value=f"Canceled test refund · {invoice['invoice_no']}",
                    )
                    retain_remaining_as_income = st.checkbox(
                        "Settle the remainder as income instead of leaving it refundable",
                        help=(
                            "When selected, the difference between the calculated refund due "
                            "and the agreed payout is recorded as retained cancellation income."
                        ),
                    )
                    if retain_remaining_as_income:
                        st.caption(
                            "Amount retained as income: "
                            f"{money(max(0.0, invoice['refund_due'] - refund_amount))}"
                        )
                    else:
                        st.caption(
                            "Any amount not paid now will remain on the patient refund list."
                        )
                    confirmed = st.checkbox(
                        f"I confirm {money(refund_amount)} was paid to {invoice['full_name']}."
                    )
                    refund_submitted = st.form_submit_button(
                        "Record patient refund",
                        type="primary",
                    )
                if refund_submitted:
                    if not confirmed:
                        st.error("Confirm that the refund was actually paid to the patient.")
                    else:
                        try:
                            with database() as connection:
                                refund = issue_patient_refund(
                                    connection,
                                    invoice["id"],
                                    refund_amount,
                                    refund_method,
                                    refund_reference.strip(),
                                    refund_reason,
                                    staff["id"],
                                    session["id"],
                                    retain_remaining_as_income,
                                )
                        except ValueError as error:
                            st.error(str(error))
                        except sqlite3.IntegrityError:
                            st.error("This transaction or voucher reference has already been used.")
                        else:
                            st.success(
                                f"Refund {money(refund['amount'])} recorded for "
                                f"{refund['patient_name']} ({refund['patient_code']}) · "
                                f"receipt REF-{refund['refund_id']:07d}."
                            )
                            if refund["retained_amount"] > 0:
                                st.info(
                                    f"{money(refund['retained_amount'])} was recorded as "
                                    "cancellation income; no additional cash payout was recorded for it."
                                )
                            st.rerun()
        else:
            st.success("No patients are currently owed a refund.")

        refund_history = db_rows(
            """SELECT rf.id AS refund_id, rf.paid_at, rf.invoice_id, i.invoice_no, p.full_name,
                      p.patient_code, rf.amount, rf.retained_amount, rf.method, rf.reference, rf.reason,
                      s.display_name AS paid_by
               FROM refunds rf JOIN invoices i ON i.id = rf.invoice_id
               JOIN visits v ON v.id = i.visit_id JOIN patients p ON p.id = v.patient_id
               LEFT JOIN staff s ON s.id = rf.paid_by
               ORDER BY rf.id DESC LIMIT 50"""
        )
        if refund_history:
            st.subheader("Refund history")
            st.dataframe(
                [
                    {
                        "Date": row["paid_at"],
                        "Receipt": f"REF-{row['refund_id']:07d}",
                        "Invoice": row["invoice_no"],
                        "Patient": row["full_name"],
                        "Patient ID": row["patient_code"],
                        "Amount": money(row["amount"]),
                        "Retained as income": money(row["retained_amount"]),
                        "Method": row["method"],
                        "Reference": row["reference"] or "—",
                        "Reason": row["reason"],
                        "Paid by": row["paid_by"] or "—",
                    }
                    for row in refund_history
                ],
                hide_index=True,
                use_container_width=True,
            )


def assignment_screen(staff):
    st.title("Test Assignment")
    samples = db_rows(
        """SELECT il.id AS line_id, i.invoice_no, p.full_name, p.patient_code,
                  il.test_name, il.department, il.status, il.assigned_to,
                  il.cancellation_reason, il.cancelled_at,
                  s.id AS sample_id, s.sample_code, COALESCE(s.status, 'Not collected') AS sample_status
           FROM invoice_lines il JOIN invoices i ON i.id = il.invoice_id
           JOIN visits v ON v.id = i.visit_id JOIN patients p ON p.id = v.patient_id
           LEFT JOIN samples s ON s.invoice_line_id = il.id ORDER BY il.id DESC"""
    )
    if not samples:
        st.info("Newly billed tests will appear here with their sample codes.")
        return
    st.dataframe(samples, hide_index=True, use_container_width=True)
    manageable_orders = [row for row in samples if row["status"] != "Cancelled"]
    if not manageable_orders:
        st.info("All billed tests have been canceled.")
        return
    choices = {
        f"{row['invoice_no']} · {row['test_name']} · {row['sample_code'] or row['sample_status']} · #{row['line_id']}": row
        for row in manageable_orders
    }
    selected = dropdown("Select test order", list(choices))
    order = choices[selected]
    st.caption(
        f"Patient: {order['full_name']} · Department: {order['department']} · "
        f"Sample: {order['sample_code'] or order['sample_status']}"
    )
    with st.form(f"assign_test_{order['line_id']}", clear_on_submit=True):
        assignee = st.text_input(
            "Assign to (department / staff / worklist)",
            value=order["assigned_to"],
        )
        reason = st.text_input("Reason for reassignment (required when changing)")
        submitted = st.form_submit_button("Save assignment")
    if submitted:
        if not assignee.strip():
            st.error("Enter the receiving department or staff name.")
        elif assignee.strip() != order["assigned_to"] and not reason.strip():
            st.error("A reason is required when reassigning a test.")
        else:
            with database() as connection:
                if assignee.strip() != order["assigned_to"]:
                    connection.execute(
                        """INSERT INTO assignment_history(invoice_line_id, old_assignee, new_assignee,
                                                           reason, changed_by, changed_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (order["line_id"], order["assigned_to"], assignee.strip(), reason.strip(),
                         staff["id"], now()),
                    )
                    audit(
                        connection,
                        staff["id"],
                        "Test reassigned",
                        "test_line",
                        order["line_id"],
                        order["assigned_to"],
                        f"{assignee.strip()}; reason={reason.strip()}",
                    )
                    connection.execute(
                        "UPDATE invoice_lines SET assigned_to = ?, assigned_at = ? WHERE id = ?",
                        (assignee.strip(), now(), order["line_id"]),
                    )
            st.success("Test assignment saved.")
            st.rerun()

    can_cancel = staff["role"] in ("Owner", "Admin", "Receptionist", "Cashier")
    if can_cancel and order["sample_id"] is None and order["status"] == "Awaiting collection":
        with st.form(f"cancel_test_{order['line_id']}", clear_on_submit=True):
            st.subheader("Cancel test before sample collection")
            cancellation_reason = st.text_input("Cancellation reason *")
            confirm_cancellation = st.checkbox(
                "I confirm this test was not sampled and its charge should be removed."
            )
            cancel_submitted = st.form_submit_button("Cancel test and adjust invoice")
        if cancel_submitted:
            if not cancellation_reason.strip():
                st.error("Enter a reason for canceling this test.")
            elif not confirm_cancellation:
                st.error("Confirm the test was not sampled before canceling it.")
            else:
                try:
                    with database() as connection:
                        cancellation = cancel_uncollected_test(
                            connection,
                            order["line_id"],
                            cancellation_reason,
                            staff["id"],
                        )
                    st.success(
                        f"{cancellation['test_name']} canceled. "
                        f"Invoice {cancellation['invoice_no']} was recalculated to "
                        f"{money(cancellation['new_net'])}."
                    )
                    if cancellation["refund_due"] > 0:
                        st.warning(
                            f"{money(cancellation['refund_due'])} is now recorded as "
                            "patient credit / refund due; payment history was preserved."
                        )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def report_delivery_screen(staff):
    st.title("Report Delivery")
    reports = db_rows(
        """SELECT rv.id AS report_version_id, rv.version, rv.issued_at, rv.issued_by,
                  il.test_name, il.department, i.invoice_no, i.due, p.full_name,
                  p.patient_code, v.age_value, v.age_unit, v.sex, s.sample_code,
                  r.status AS result_status, r.result_summary, r.verified_by, r.verified_at
           FROM report_versions rv JOIN invoice_lines il ON il.id = rv.invoice_line_id
           JOIN invoices i ON i.id = il.invoice_id JOIN visits v ON v.id = i.visit_id
           JOIN patients p ON p.id = v.patient_id JOIN results r ON r.id = rv.result_id
           LEFT JOIN samples s ON s.invoice_line_id = il.id
           WHERE rv.authorized = 1 AND r.status = 'Verified'
             AND NOT EXISTS (SELECT 1 FROM report_deliveries rd WHERE rd.report_version_id = rv.id)
           ORDER BY rv.issued_at"""
    )
    visible_reports = [
        row for row in reports if row["due"] <= 0.005 or staff["role"] in ("Owner", "Admin")
    ]
    if not visible_reports:
        if reports:
            st.warning("Reports with unpaid test charges are held for an Owner/Admin release.")
            st.caption("Settle the due first, or have an Owner/Admin authorize an exception.")
        else:
            st.info("No undelivered, verified and authorized reports are available. Unauthorized reports cannot be released.")
    else:
        st.dataframe(visible_reports, hide_index=True, use_container_width=True)
        choices = {
            f"{r['invoice_no']} · {r['full_name']} · {r['test_name']} · v{r['version']} · Due {money(r['due'])}": r
            for r in visible_reports
        }
        selected = dropdown("Report to release", list(choices))
        report = choices[selected]
        st.subheader("Authorized report")
        st.write(
            f"**Patient:** {report['full_name']} · {report['patient_code']} · "
            f"**Test:** {report['test_name']} · **Version:** {report['version']}"
        )
        st.text(report["result_summary"])
        st.download_button(
            "Download printable report",
            printable_report_html(report),
            file_name=f"{report['invoice_no']}-report-v{report['version']}.html",
            mime="text/html",
        )
        with st.form("release_report", clear_on_submit=True):
            recipient = st.text_input("Collected by (optional)")
            relationship = st.text_input("Relationship (optional)")
            confirmed = st.checkbox("I verified that this is the authorized final report.")
            override_reason = ""
            if report["due"] > 0.005:
                override_reason = st.text_input("Owner/Admin override reason *")
            submitted = st.form_submit_button("Record report delivery", type="primary")
        if submitted:
            if not confirmed:
                st.error("Confirm the report version before release.")
            elif report["due"] > 0.005 and (staff["role"] not in ("Owner", "Admin") or not override_reason.strip()):
                st.error("Only an Owner/Admin can release a report with due; an override reason is required.")
            else:
                with database() as connection:
                    connection.execute(
                        """INSERT INTO report_deliveries(report_version_id, delivered_to, relationship, delivered_by, delivered_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (report["report_version_id"], recipient.strip() or "Not recorded",
                         relationship.strip(), staff["id"], now()),
                    )
                    audit(
                        connection,
                        staff["id"],
                        "Report handed over",
                        "report",
                        report["report_version_id"],
                        "",
                        f"invoice={report['invoice_no']}; due={report['due']:.2f}; override={override_reason.strip()}",
                    )
                st.success("Authorized report delivery recorded.")
                st.rerun()
    history = db_rows(
        """SELECT i.invoice_no, p.full_name, il.test_name, rv.version, rd.delivered_to,
                  rd.relationship, rd.delivered_at
           FROM report_deliveries rd JOIN report_versions rv ON rv.id = rd.report_version_id
           JOIN invoice_lines il ON il.id = rv.invoice_line_id JOIN invoices i ON i.id = il.invoice_id
           JOIN visits v ON v.id = i.visit_id JOIN patients p ON p.id = v.patient_id
           ORDER BY rd.id DESC LIMIT 30"""
    )
    st.subheader("Delivery history")
    if history:
        st.dataframe(history, hide_index=True, use_container_width=True)
    else:
        st.caption("No reports have been delivered yet.")


def inventory_screen(staff):
    st.title("Inventory")
    can_manage_stock = staff["role"] in ("Owner", "Admin")
    if not can_manage_stock:
        st.info("Inventory is view-only for this role. Stock corrections require Owner/Admin permission.")
    items = db_rows("SELECT * FROM stock_items ORDER BY name")
    if items:
        st.dataframe(
            [
                {**item, "status": "Reorder" if item["on_hand"] <= item["reorder_level"] else "In stock"}
                for item in items
            ],
            hide_index=True,
            use_container_width=True,
        )
    with st.expander("Record stock movement", expanded=not items):
        item_options = {item["name"]: item for item in items}
        with st.form("stock_movement", clear_on_submit=True):
            existing = dropdown("Item", ["Add a new item"] + list(item_options))
            new_name = st.text_input("New item name")
            unit = st.text_input("Unit (piece, box, ml...)")
            movement_type = dropdown("Movement", ("Stock received", "Usage / issued", "Wastage", "Correction"))
            quantity = st.number_input("Quantity", min_value=0.01, value=1.0, step=1.0)
            reorder = st.number_input("Reorder level (new item)", min_value=0.0, value=0.0, step=1.0)
            note = st.text_input("Note / reference")
            submitted = st.form_submit_button("Save movement", disabled=not can_manage_stock)
        if submitted:
            if existing == "Add a new item" and (not new_name.strip() or not unit.strip()):
                st.error("Enter the new item name and unit.")
            elif movement_type in ("Usage / issued", "Wastage", "Correction") and not note.strip():
                st.error("Enter a reason or reference for this stock movement.")
            else:
                signed_quantity = quantity if movement_type == "Stock received" else -quantity if movement_type in ("Usage / issued", "Wastage") else quantity
                try:
                    with database() as connection:
                        if existing == "Add a new item":
                            cursor = connection.execute(
                                "INSERT INTO stock_items(name, unit, on_hand, reorder_level) VALUES (?, ?, 0, ?)",
                                (new_name.strip(), unit.strip(), reorder),
                            )
                            item_id = cursor.lastrowid
                        else:
                            item_id = item_options[existing]["id"]
                            if movement_type == "Correction":
                                signed_quantity = quantity - item_options[existing]["on_hand"]
                                if abs(signed_quantity) < 0.0001:
                                    st.info("Stock count already matches; no movement was recorded.")
                                    return
                        stock_balance = connection.execute(
                            "SELECT on_hand, average_cost_paisa FROM stock_items WHERE id = ?",
                            (item_id,),
                        ).fetchone()
                        current_qty = stock_balance["on_hand"]
                        movement_at = now()
                        connection.execute("UPDATE stock_items SET on_hand = on_hand + ? WHERE id = ?", (signed_quantity, item_id))
                        movement_cursor = connection.execute(
                            """INSERT INTO stock_movements(stock_item_id, quantity, movement_type, note, created_by, created_at)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (item_id, signed_quantity, movement_type, note.strip(), staff["id"], movement_at),
                        )
                        inventory_value_paisa = int(
                            round(abs(signed_quantity) * stock_balance["average_cost_paisa"])
                        )
                        if inventory_value_paisa > 0 and movement_type != "Stock received":
                            if movement_type == "Usage / issued":
                                debit_account = "consumables_expense"
                                credit_account = "inventory"
                            elif movement_type == "Wastage" or signed_quantity < 0:
                                debit_account = "cash_variance"
                                credit_account = "inventory"
                            else:
                                debit_account = "inventory"
                                credit_account = "other_income"
                            post_journal_entry(
                                connection,
                                movement_at[:10],
                                f"Inventory movement · {item_options[existing]['name'] if existing != 'Add a new item' else new_name.strip()}",
                                [
                                    {
                                        "account_key": debit_account,
                                        "debit_paisa": inventory_value_paisa,
                                        "description": note.strip(),
                                    },
                                    {
                                        "account_key": credit_account,
                                        "credit_paisa": inventory_value_paisa,
                                        "description": note.strip(),
                                    },
                                ],
                                created_by=staff["id"],
                                source_type="Inventory movement",
                                source_key=f"inventory-movement:{movement_cursor.lastrowid}",
                                source_id=movement_cursor.lastrowid,
                            )
                        audit(
                            connection,
                            staff["id"],
                            "Stock movement",
                            "stock_item",
                            item_id,
                            f"on_hand={current_qty:g}",
                            f"on_hand={current_qty + signed_quantity:g}; type={movement_type}; reason={note.strip()}",
                        )
                    st.success("Stock movement recorded.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Could not save this item. Check that the item name is unique.")
    movements = db_rows(
        """SELECT sm.created_at, si.name, sm.quantity, si.unit, sm.movement_type, sm.note
           FROM stock_movements sm JOIN stock_items si ON si.id = sm.stock_item_id
           ORDER BY sm.id DESC LIMIT 30"""
    )
    st.subheader("Recent movements")
    if movements:
        st.dataframe(movements, hide_index=True, use_container_width=True)
    else:
        st.caption("No stock movements recorded.")


def day_management(staff):
    st.title("Day Open / Close")
    st.caption("A business day stays open until it is reconciled; it does not reset at midnight.")
    st.warning("This standalone build stores data on one device; it does not yet provide the cloud offline queue or sync checks.")
    non_cash_methods = [method for method in PAYMENT_METHODS if method != "Cash"]
    session = current_session()
    if session is None:
        st.subheader("Open cashier day")
        with st.form("open_day", clear_on_submit=True):
            opening_cash = st.number_input("Opening cash float (৳)", min_value=0.0, value=0.0, step=500.0)
            opening_channels = {
                method: st.number_input(
                    f"Opening {method} balance (৳)",
                    min_value=0.0,
                    value=0.0,
                    step=500.0,
                    key=f"opening_{method}",
                )
                for method in non_cash_methods
            }
            submitted = st.form_submit_button("Open day", type="primary")
        if submitted:
            with database() as connection:
                cursor = connection.execute(
                    "INSERT INTO day_sessions(opened_by, opened_at, opening_cash) VALUES (?, ?, ?)",
                    (staff["id"], now(), opening_cash),
                )
                session_id = cursor.lastrowid
                connection.executemany(
                    """INSERT INTO day_channel_balances(day_session_id, method, opening_balance)
                       VALUES (?, ?, ?)""",
                    [(session_id, method, value) for method, value in opening_channels.items()],
                )
                audit(connection, staff["id"], "Business day opened", "day_session", session_id, "", f"opening_cash={opening_cash:.2f}")
            st.success("Cashier day opened.")
            st.rerun()
    else:
        ledger = db_rows(
            "SELECT direction, amount, method, entry_type, description, created_at FROM ledger WHERE day_session_id = ? ORDER BY id",
            (session["id"],),
        )
        cash_in = sum(x["amount"] for x in ledger if x["direction"] == "in" and x["method"] == "Cash")
        cash_out = sum(x["amount"] for x in ledger if x["direction"] == "out" and x["method"] == "Cash")
        expected = float(session["opening_cash"]) + cash_in - cash_out
        st.success(f"Day open since {session['opened_at']} · Opening float {money(session['opening_cash'])}")
        metrics = st.columns(3)
        money_metric(metrics[0], "Cash received", cash_in)
        money_metric(metrics[1], "Cash paid out", cash_out)
        money_metric(metrics[2], "Expected drawer", expected)
        st.subheader("Mobile wallet / bank balances")
        with database() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO day_channel_balances(day_session_id, method, opening_balance)
                   VALUES (?, ?, 0)""",
                [(session["id"], method) for method in non_cash_methods],
            )
        channel_openings = {
            row["method"]: row["opening_balance"]
            for row in db_rows(
                "SELECT method, opening_balance FROM day_channel_balances WHERE day_session_id = ?",
                (session["id"],),
            )
        }
        channel_expected = {}
        channel_ledger = {}
        for method in non_cash_methods:
            opening = float(channel_openings.get(method, 0))
            channel_in = sum(
                item["amount"] for item in ledger
                if item["method"] == method and item["direction"] == "in"
            )
            channel_out = sum(
                item["amount"] for item in ledger
                if item["method"] == method and item["direction"] == "out"
            )
            channel_expected[method] = opening + channel_in - channel_out
            channel_ledger[method] = (channel_in, channel_out)
        st.dataframe(
            [
                {
                    "Method": method,
                    "Opening": money(channel_openings.get(method, 0)),
                    "Received": money(channel_ledger[method][0]),
                    "Paid out": money(channel_ledger[method][1]),
                    "Expected balance": money(channel_expected[method]),
                }
                for method in non_cash_methods
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.subheader("Cash expense / payout")
        with st.form("cash_expense", clear_on_submit=True):
            expense_amount = st.number_input("Cash paid out (৳)", min_value=0.01, value=100.0, step=50.0)
            expense_note = st.text_input("Reason / voucher reference")
            expense_submitted = st.form_submit_button("Record cash payout")
        if expense_submitted:
            if not expense_note.strip():
                st.error("Enter a reason for the payout.")
            else:
                with database() as connection:
                    payout_at = now()
                    payout_cursor = connection.execute(
                        """INSERT INTO ledger(day_session_id, direction, amount, method, entry_type, description, created_by, created_at)
                           VALUES (?, 'out', ?, 'Cash', 'Expense', ?, ?, ?)""",
                        (session["id"], expense_amount, expense_note.strip(), staff["id"], payout_at),
                    )
                    payout_id = payout_cursor.lastrowid
                    post_journal_entry(
                        connection,
                        payout_at[:10],
                        f"Cash payout · {expense_note.strip()}",
                        [
                            {
                                "account_key": "miscellaneous_expense",
                                "debit": expense_amount,
                                "description": expense_note.strip(),
                            },
                            {
                                "account_key": "cash_cash",
                                "credit": expense_amount,
                                "description": expense_note.strip(),
                            },
                        ],
                        created_by=staff["id"],
                        source_type="Cash expense",
                        source_key=f"cash-expense:{payout_id}",
                        source_id=payout_id,
                    )
                    audit(connection, staff["id"], "Cash expense recorded", "day_session", session["id"], "", f"amount={expense_amount:.2f}; reason={expense_note.strip()}")
                st.success("Payout recorded.")
                st.rerun()
        if ledger:
            st.subheader("Shift ledger")
            visible_ledger = ledger if staff["role"] == "Owner" else [
                row for row in ledger if row["entry_type"] != "Commission"
            ]
            st.dataframe(visible_ledger, hide_index=True, use_container_width=True)
        st.subheader("Close and reconcile")
        with st.form("close_day", clear_on_submit=True):
            counted_cash = st.number_input("Counted drawer cash (৳)", min_value=0.0, value=max(0.0, expected), step=100.0)
            counted_channels = {
                method: st.number_input(
                    f"Counted {method} balance (৳)",
                    min_value=0.0,
                    value=max(0.0, channel_expected[method]),
                    step=100.0,
                    key=f"counted_{method}",
                )
                for method in non_cash_methods
            }
            notes = st.text_input("Variance reason / closing notes")
            submitted = st.form_submit_button("Close day", type="primary")
        if submitted:
            variance = counted_cash - expected
            channel_variances = {
                method: counted_channels[method] - channel_expected[method]
                for method in non_cash_methods
            }
            if (abs(variance) > 0.005 or any(abs(value) > 0.005 for value in channel_variances.values())) and not notes.strip():
                st.error("Enter a reason for any cash, mobile wallet or bank variance before closing.")
                return
            with database() as connection:
                close_at = now()
                connection.execute(
                    """UPDATE day_sessions SET closed_by = ?, closed_at = ?, expected_cash = ?,
                       counted_cash = ?, variance = ?, notes = ? WHERE id = ?""",
                    (staff["id"], close_at, expected, counted_cash, variance, notes.strip(), session["id"]),
                )
                for method in non_cash_methods:
                    connection.execute(
                        """UPDATE day_channel_balances SET expected_balance = ?, counted_balance = ?, variance = ?
                           WHERE day_session_id = ? AND method = ?""",
                        (channel_expected[method], counted_channels[method], channel_variances[method], session["id"], method),
                    )
                total_variance = round(variance + sum(channel_variances.values()), 2)
                if abs(total_variance) > 0.005:
                    variance_lines = []
                    cash_variance_by_method = {"Cash": variance, **channel_variances}
                    for method, method_variance in cash_variance_by_method.items():
                        if abs(method_variance) <= 0.005:
                            continue
                        cash_key = cash_account_key(method)
                        if method_variance > 0:
                            variance_lines.append(
                                {
                                    "account_key": cash_key,
                                    "debit": method_variance,
                                    "description": f"{method} reconciliation surplus",
                                }
                            )
                        else:
                            variance_lines.append(
                                {
                                    "account_key": cash_key,
                                    "credit": abs(method_variance),
                                    "description": f"{method} reconciliation shortage",
                                }
                            )
                    if total_variance > 0:
                        variance_lines.append(
                            {
                                "account_key": "cash_variance_income",
                                "credit": total_variance,
                                "description": "Net cashier reconciliation surplus",
                            }
                        )
                    else:
                        variance_lines.append(
                            {
                                "account_key": "cash_variance",
                                "debit": abs(total_variance),
                                "description": "Net cashier reconciliation shortage",
                            }
                        )
                    post_journal_entry(
                        connection,
                        close_at[:10],
                        f"Cashier day variance · {session['id']}",
                        variance_lines,
                        created_by=staff["id"],
                        source_type="Cash variance",
                        source_key=f"day-variance:{session['id']}",
                        source_id=session["id"],
                    )
                audit(
                    connection,
                    staff["id"],
                    "Business day closed",
                    "day_session",
                    session["id"],
                    f"expected_cash={expected:.2f}",
                    f"counted_cash={counted_cash:.2f}; cash_variance={variance:.2f}; "
                    f"channel_variances={channel_variances}; reason={notes.strip()}",
                )
            st.success(f"Day closed. Cash variance: {money(variance)}")
            st.rerun()
    history = db_rows(
        """SELECT opened_at, closed_at, opening_cash, expected_cash, counted_cash, variance, notes
           FROM day_sessions WHERE closed_at IS NOT NULL ORDER BY id DESC LIMIT 15"""
    )
    st.subheader("Recent closed days")
    if history:
        st.dataframe(history, hide_index=True, use_container_width=True)
    else:
        st.caption("No closed-day reconciliations yet.")


def account_management(staff):
    st.title("Accounts & Referrers")
    if staff["role"] not in ("Owner", "Admin"):
        st.warning("Only an Owner or Admin can manage staff accounts and catalog records.")
        return
    if st.session_state.pop("new_staff_account_reset_pending", False):
        for key in ("new_staff_name", "staff_username", "new_staff_role", "new_staff_pin"):
            st.session_state.pop(key, None)
    tab_names = [
        "User Management" if staff["role"] == "Owner" else "Staff accounts",
        "Test catalog",
        "Referrers",
        "Roles & Rights",
    ]
    if staff["role"] == "Owner":
        tab_names.append("Commission")
    tabs = st.tabs(tab_names)
    staff_tab, test_tab, referral_tab, roles_tab = tabs[:4]
    with staff_tab:
        if staff["role"] == "Owner":
            st.subheader("User Management")
        staff_rows = db_rows(
            "SELECT id, username, display_name, role, active, created_at FROM staff ORDER BY display_name"
        )
        st.dataframe(
            [{key: value for key, value in row.items() if key != "id"} for row in staff_rows],
            hide_index=True,
            use_container_width=True,
        )
        available_roles = (
            ("Admin", "Receptionist", "Cashier", "Lab Tech")
            if staff["role"] == "Owner"
            else ("Receptionist", "Cashier", "Lab Tech")
        )
        st.subheader("Add staff account")
        display_name = st.text_input("Staff name", key="new_staff_name")
        username = st.text_input("Username", key="staff_username")
        role = dropdown("Role", available_roles, key="new_staff_role")
        st.caption(f"Selected role: {role}")
        password = st.text_input("PIN (4–6 digits)", type="password", key="new_staff_pin")
        submitted = st.button("Create account", type="primary")
        if submitted:
            if not display_name.strip() or not username.strip() or not password.isdigit() or not 4 <= len(password) <= 6:
                st.error("Enter a name, username and a PIN of 4–6 digits.")
            else:
                try:
                    if staff_username_is_taken(
                        username, st.session_state["tenant_id"]
                    ):
                        raise ValueError(
                            "Usernames must be unique across diagnostic centers."
                        )
                    with database() as connection:
                        cursor = connection.execute(
                            """INSERT INTO staff(username, display_name, password_hash, role, created_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            (username.strip().lower(), display_name.strip(), password_digest(password), role, now()),
                        )
                        audit(
                            connection,
                            staff["id"],
                            "Staff account created",
                            "staff",
                            cursor.lastrowid,
                            "",
                            f"{username.strip().lower()}; {role}",
                        )
                    st.success("Account created.")
                    st.session_state["new_staff_account_reset_pending"] = True
                    st.rerun()
                except (ValueError, RuntimeError, sqlite3.Error) as error:
                    st.error(str(error) or "The username could not be verified.")

        accounts = db_rows(
            "SELECT id, username, display_name, role, active, locked FROM staff ORDER BY display_name"
        )
        manageable_accounts = [
            row for row in accounts
            if row["id"] != staff["id"]
            and (staff["role"] == "Owner" or row["role"] in ("Receptionist", "Cashier", "Lab Tech"))
        ]
        if manageable_accounts:
            account_map = {
                f"{row['display_name']} · {row['username']}": row
                for row in manageable_accounts
            }
            st.subheader("Manage staff account")
            selected_label = dropdown("Account to manage", list(account_map))
            selected = account_map[selected_label]
            action_columns = st.columns(4)
            if action_columns[0].button("Edit account", key=f"edit_staff_{selected['id']}"):
                st.session_state["editing_staff_id"] = selected["id"]
                st.session_state.pop("deleting_staff_id", None)
                st.rerun()
            desired_active = not bool(selected["active"])
            if action_columns[1].button(
                "Reactivate account" if desired_active else "Deactivate account",
                key=f"toggle_staff_{selected['id']}",
            ):
                with database() as connection:
                    connection.execute(
                        "UPDATE staff SET active = ? WHERE id = ?",
                        (int(desired_active), selected["id"]),
                    )
                    audit(
                        connection,
                        staff["id"],
                        "Staff access changed",
                        "staff",
                        selected["id"],
                        str(selected["active"]),
                        str(int(desired_active)),
                    )
                st.success("Account access updated.")
                st.rerun()
            if action_columns[2].button(
                "Delete account",
                key=f"delete_staff_{selected['id']}",
            ):
                st.session_state["deleting_staff_id"] = selected["id"]
                st.session_state.pop("editing_staff_id", None)
                st.rerun()
            if selected["locked"] and action_columns[3].button(
                "Reset PIN lock",
                key=f"reset_staff_lock_{selected['id']}",
            ):
                with database() as connection:
                    connection.execute(
                        "UPDATE staff SET failed_attempts = 0, locked = 0 WHERE id = ?",
                        (selected["id"],),
                    )
                    audit(connection, staff["id"], "Staff PIN lock reset", "staff", selected["id"])
                st.success("PIN lock reset.")
                st.rerun()
            st.caption(
                "The currently signed-in account cannot be changed or deleted here. "
                "Accounts with linked history cannot be permanently deleted; deactivate them instead."
            )

            editing_staff_id = st.session_state.get("editing_staff_id")
            editing_staff = next(
                (row for row in accounts if row["id"] == editing_staff_id),
                None,
            )
            if editing_staff:
                st.subheader("Edit User Details")
                with st.form(
                    f"edit_staff_form_{editing_staff['id']}",
                    clear_on_submit=True,
                ):
                    edited_name = st.text_input(
                        "Staff name",
                        value=editing_staff["display_name"],
                        key=f"edit_staff_name_{editing_staff['id']}",
                    )
                    edited_username = st.text_input(
                        "Username",
                        value=editing_staff["username"],
                        key=f"edit_staff_username_{editing_staff['id']}",
                    )
                    role_options = available_roles
                    if editing_staff["role"] not in role_options:
                        role_options = (editing_staff["role"],) + role_options
                    edited_role = st.selectbox(
                        "Role",
                        role_options,
                        index=role_options.index(editing_staff["role"]),
                        key=f"edit_staff_role_{editing_staff['id']}",
                    )
                    new_password = st.text_input(
                        "New PIN (leave blank to keep current)",
                        type="password",
                        key=f"edit_staff_pin_{editing_staff['id']}",
                    )
                    save_staff = st.form_submit_button("Save account changes", type="primary")
                if save_staff:
                    normalized_username = edited_username.strip().lower()
                    if not edited_name.strip() or not normalized_username:
                        st.error("Enter both a staff name and username.")
                    elif new_password and (not new_password.isdigit() or not 4 <= len(new_password) <= 6):
                        st.error("The new PIN must contain 4–6 digits.")
                    else:
                        try:
                            if staff_username_is_taken(
                                normalized_username,
                                st.session_state["tenant_id"],
                                editing_staff["id"],
                            ):
                                raise ValueError(
                                    "Usernames must be unique across diagnostic centers."
                                )
                            with database() as connection:
                                connection.execute(
                                    """UPDATE staff SET username = ?, display_name = ?, role = ?,
                                       password_hash = CASE WHEN ? = '' THEN password_hash ELSE ? END
                                       WHERE id = ?""",
                                    (
                                        normalized_username,
                                        edited_name.strip(),
                                        edited_role,
                                        new_password,
                                        password_digest(new_password) if new_password else "",
                                        editing_staff["id"],
                                    ),
                                )
                                audit(
                                    connection,
                                    staff["id"],
                                    "Staff account updated",
                                    "staff",
                                    editing_staff["id"],
                                    f"{editing_staff['username']}; {editing_staff['display_name']}; {editing_staff['role']}",
                                    f"{normalized_username}; {edited_name.strip()}; {edited_role}",
                                )
                            st.session_state.pop("editing_staff_id", None)
                            st.success("Account changes saved.")
                            st.rerun()
                        except (ValueError, RuntimeError, sqlite3.Error) as error:
                            st.error(str(error) or "The username could not be verified.")
                if st.button("Cancel account edit", key=f"cancel_edit_staff_{editing_staff['id']}"):
                    st.session_state.pop("editing_staff_id", None)
                    st.rerun()

            deleting_staff_id = st.session_state.get("deleting_staff_id")
            deleting_staff = next(
                (row for row in accounts if row["id"] == deleting_staff_id),
                None,
            )
            if deleting_staff:
                st.warning(
                    f"Delete account for “{deleting_staff['display_name']}” "
                    f"({deleting_staff['username']})? This cannot be undone."
                )
                confirm_delete, cancel_delete = st.columns(2)
                if confirm_delete.button(
                    f"Confirm delete {deleting_staff['display_name']}",
                    type="primary",
                    key=f"confirm_delete_staff_{deleting_staff_id}",
                ):
                    with database() as connection:
                        reference_count = foreign_key_reference_count(
                            connection, "staff", deleting_staff_id
                        )
                        if reference_count:
                            deletion_blocked = True
                        else:
                            deletion_blocked = False
                            audit(
                                connection,
                                staff["id"],
                                "Staff account deleted",
                                "staff",
                                deleting_staff_id,
                                f"{deleting_staff['username']}; {deleting_staff['display_name']}",
                                "",
                            )
                            connection.execute(
                                "DELETE FROM staff WHERE id = ?",
                                (deleting_staff_id,),
                            )
                    if deletion_blocked:
                        st.error(
                            f"“{deleting_staff['display_name']}” has linked operational or audit history "
                            "and cannot be permanently deleted. Deactivate the account instead."
                        )
                    else:
                        st.session_state.pop("deleting_staff_id", None)
                        st.success("Account deleted.")
                        st.rerun()
                if cancel_delete.button("Cancel", key=f"cancel_delete_staff_{deleting_staff_id}"):
                    st.session_state.pop("deleting_staff_id", None)
                    st.rerun()
        else:
            st.caption("No other staff accounts are available to manage.")
    with test_tab:
        test_rows = db_rows(
            "SELECT id, code, name, department, price, active FROM tests ORDER BY department, name"
        )
        st.dataframe(
            [{key: value for key, value in row.items() if key != "id"} for row in test_rows],
            hide_index=True,
            use_container_width=True,
        )
        test_map = {f"{item['code']} · {item['name']}": item for item in test_rows}
        if test_map:
            selected_test_label = dropdown("Test to manage", list(test_map))
            selected_test = test_map[selected_test_label]
            test_actions = st.columns(3)
            if test_actions[0].button("Edit test", key=f"edit_test_{selected_test['id']}"):
                st.session_state["editing_test_id"] = selected_test["id"]
                st.session_state.pop("deleting_test_id", None)
                st.rerun()
            desired_test_active = not bool(selected_test["active"])
            if test_actions[1].button(
                "Reactivate test" if desired_test_active else "Deactivate test",
                key=f"toggle_test_{selected_test['id']}",
            ):
                with database() as connection:
                    connection.execute(
                        "UPDATE tests SET active = ? WHERE id = ?",
                        (int(desired_test_active), selected_test["id"]),
                    )
                    audit(
                        connection,
                        staff["id"],
                        "Test availability changed",
                        "test",
                        selected_test["id"],
                        str(selected_test["active"]),
                        str(int(desired_test_active)),
                    )
                st.rerun()
            if test_actions[2].button(
                "Delete test",
                key=f"delete_test_{selected_test['id']}",
            ):
                st.session_state["deleting_test_id"] = selected_test["id"]
                st.session_state.pop("editing_test_id", None)
                st.rerun()

            editing_test_id = st.session_state.get("editing_test_id")
            editing_test = next(
                (row for row in test_rows if row["id"] == editing_test_id),
                None,
            )
            if editing_test:
                st.subheader("Edit Test Details")
                with st.form(
                    f"edit_test_form_{editing_test['id']}",
                    clear_on_submit=True,
                ):
                    edited_code = st.text_input(
                        "Test code",
                        value=editing_test["code"],
                        key=f"edit_test_code_{editing_test['id']}",
                    )
                    edited_name = st.text_input(
                        "Test name",
                        value=editing_test["name"],
                        key=f"edit_test_name_{editing_test['id']}",
                    )
                    department_options = ("Laboratory", "Imaging", "Cardiology", "Other")
                    if editing_test["department"] not in department_options:
                        department_options = (editing_test["department"],) + department_options
                    edited_department = st.selectbox(
                        "Department",
                        department_options,
                        index=department_options.index(editing_test["department"]),
                        key=f"edit_test_department_{editing_test['id']}",
                    )
                    edited_price = st.number_input(
                        "Price (৳)",
                        min_value=0.0,
                        value=float(editing_test["price"]),
                        step=50.0,
                        key=f"edit_test_price_{editing_test['id']}",
                    )
                    save_test = st.form_submit_button("Save test changes", type="primary")
                if save_test:
                    normalized_code = edited_code.strip().upper()
                    if not normalized_code or not edited_name.strip():
                        st.error("Enter both a test code and name.")
                    else:
                        try:
                            with database() as connection:
                                connection.execute(
                                    """UPDATE tests SET code = ?, name = ?, department = ?, price = ?
                                       WHERE id = ?""",
                                    (
                                        normalized_code,
                                        edited_name.strip(),
                                        edited_department,
                                        edited_price,
                                        editing_test["id"],
                                    ),
                                )
                                audit(
                                    connection,
                                    staff["id"],
                                    "Test updated",
                                    "test",
                                    editing_test["id"],
                                    f"{editing_test['code']}; {editing_test['name']}; "
                                    f"{editing_test['department']}; {editing_test['price']:.2f}",
                                    f"{normalized_code}; {edited_name.strip()}; "
                                    f"{edited_department}; {edited_price:.2f}",
                                )
                            st.session_state.pop("editing_test_id", None)
                            st.success("Test changes saved.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("That test code is already in use.")
                if st.button("Cancel test edit", key=f"cancel_edit_test_{editing_test['id']}"):
                    st.session_state.pop("editing_test_id", None)
                    st.rerun()

            deleting_test_id = st.session_state.get("deleting_test_id")
            deleting_test = next(
                (row for row in test_rows if row["id"] == deleting_test_id),
                None,
            )
            if deleting_test:
                st.warning(
                    f"Delete test “{deleting_test['name']}” ({deleting_test['code']})? "
                    "This permanently removes the catalog record if no invoice lines depend on it."
                )
                confirm_delete, cancel_delete = st.columns(2)
                if confirm_delete.button(
                    f"Confirm delete {deleting_test['code']}",
                    type="primary",
                    key=f"confirm_delete_test_{deleting_test_id}",
                ):
                    with database() as connection:
                        reference_count = foreign_key_reference_count(
                            connection, "tests", deleting_test_id
                        )
                        if reference_count:
                            deletion_blocked = True
                        else:
                            deletion_blocked = False
                            audit(
                                connection,
                                staff["id"],
                                "Test deleted",
                                "test",
                                deleting_test_id,
                                f"{deleting_test['code']}; {deleting_test['name']}",
                                "",
                            )
                            connection.execute(
                                "DELETE FROM tests WHERE id = ?",
                                (deleting_test_id,),
                            )
                    if deletion_blocked:
                        st.error(
                            f"“{deleting_test['name']}” is linked to invoice history and cannot "
                            "be deleted. Deactivate it instead to hide it from new invoices."
                        )
                    else:
                        st.session_state.pop("deleting_test_id", None)
                        st.success("Test deleted.")
                        st.rerun()
                if cancel_delete.button("Cancel", key=f"cancel_delete_test_{deleting_test_id}"):
                    st.session_state.pop("deleting_test_id", None)
                    st.rerun()
        else:
            st.info("No tests are in the catalog.")

        with st.form("new_test", clear_on_submit=True):
            st.subheader("Add test")
            code = st.text_input("Test code")
            name = st.text_input("Test name")
            department = dropdown("Department", ("Laboratory", "Imaging", "Cardiology", "Other"))
            price = st.number_input("Price (৳)", min_value=0.0, value=0.0, step=50.0)
            submitted = st.form_submit_button("Add test")
        if submitted:
            try:
                with database() as connection:
                    cursor = connection.execute(
                        "INSERT INTO tests(code, name, department, price) VALUES (?, ?, ?, ?)",
                        (code.strip().upper(), name.strip(), department, price),
                    )
                    audit(
                        connection,
                        staff["id"],
                        "Test added",
                        "test",
                        cursor.lastrowid,
                        "",
                        f"{code.strip().upper()}; {name.strip()}; price={price:.2f}",
                    )
                st.success("Test added.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Test code must be unique; enter a code and name.")
    with referral_tab:
        referrer_sql = (
            """SELECT id, name, referrer_type, phone, commission_percent, commission_type,
                      commission_amount, active FROM referrers ORDER BY name"""
            if staff["role"] == "Owner"
            else "SELECT id, name, referrer_type, phone, active FROM referrers ORDER BY name"
        )
        refs = db_rows(referrer_sql)
        if staff["role"] == "Owner":
            referrer_columns = st.columns([3, 1.4, 1.5, 1, 0.8, 0.7, 0.7])
            headers = ("Referrer", "Type", "Phone", "Commission", "Status", "Edit", "Delete")
        else:
            referrer_columns = st.columns([3.5, 1.5, 2, 1, 0.7, 0.7])
            headers = ("Referrer", "Type", "Phone", "Status", "Edit", "Delete")
        for column, header in zip(referrer_columns, headers):
            column.markdown(f"**{header}**")
        if refs:
            for referrer in refs:
                row = st.columns([3, 1.4, 1.5, 1, 0.8, 0.7, 0.7] if staff["role"] == "Owner"
                                else [3.5, 1.5, 2, 1, 0.7, 0.7])
                values = [
                    referrer["name"],
                    referrer["referrer_type"],
                    referrer["phone"] or "—",
                ]
                if staff["role"] == "Owner":
                    values.append(commission_description(referrer))
                values.append("Active" if referrer["active"] else "Inactive")
                for column, value in zip(row, values):
                    column.write(value)
                action_offset = len(values)
                with row[action_offset]:
                    if st.button(
                        "✏️",
                        key=f"edit_referrer_row_{referrer['id']}",
                        help=f"Edit {referrer['name']}",
                    ):
                        st.session_state["editing_referrer_id"] = referrer["id"]
                        st.session_state.pop("deleting_referrer_id", None)
                        st.rerun()
                with row[action_offset + 1]:
                    if st.button(
                        "🗑️",
                        key=f"delete_referrer_row_{referrer['id']}",
                        help=f"Delete {referrer['name']}",
                    ):
                        st.session_state["deleting_referrer_id"] = referrer["id"]
                        st.session_state.pop("editing_referrer_id", None)
                        st.rerun()
        else:
            st.info("No referrers have been added yet.")

        deleting_referrer_id = st.session_state.get("deleting_referrer_id")
        deleting_referrer = next(
            (referrer for referrer in refs if referrer["id"] == deleting_referrer_id),
            None,
        )
        if deleting_referrer:
            st.warning(
                f"Delete referrer “{deleting_referrer['name']}”? "
                "This permanently removes the referrer record if no invoices or "
                "commission entries depend on it."
            )
            confirm_delete, cancel_delete = st.columns(2)
            with confirm_delete:
                confirm_delete_clicked = st.button(
                    f"Confirm delete {deleting_referrer['name']}",
                    type="primary",
                    key=f"confirm_delete_referrer_{deleting_referrer_id}",
                )
            with cancel_delete:
                cancel_delete_clicked = st.button(
                    "Cancel",
                    key=f"cancel_delete_referrer_{deleting_referrer_id}",
                )
            if cancel_delete_clicked:
                st.session_state.pop("deleting_referrer_id", None)
                st.rerun()
            if confirm_delete_clicked:
                referrer_id = deleting_referrer["id"]
                blocked_message = None
                with database() as connection:
                    dependencies = connection.execute(
                        """SELECT
                             (SELECT COUNT(*) FROM invoices
                              WHERE referrer_id = ? OR ordered_by_referrer_id = ?) AS invoice_count,
                             (SELECT COUNT(*) FROM commission_entries WHERE referrer_id = ?) AS commission_count""",
                        (referrer_id, referrer_id, referrer_id),
                    ).fetchone()
                    if dependencies["invoice_count"] or dependencies["commission_count"]:
                        blocked_message = (
                            f"“{deleting_referrer['name']}” is linked to "
                            f"{dependencies['invoice_count']} invoice(s) and "
                            f"{dependencies['commission_count']} commission record(s). "
                            "It cannot be permanently deleted without damaging history. "
                            "Use Edit to deactivate it instead."
                        )
                    else:
                        audit(
                            connection,
                            staff["id"],
                            "Referrer deleted",
                            "referrer",
                            referrer_id,
                            (
                                f"name={deleting_referrer['name']}; "
                                f"type={deleting_referrer['referrer_type']}; "
                                f"phone={deleting_referrer['phone']}"
                            ),
                            "",
                        )
                        connection.execute(
                            "DELETE FROM referrers WHERE id = ?",
                            (referrer_id,),
                        )
                if blocked_message:
                    st.error(blocked_message)
                else:
                    st.session_state.pop("deleting_referrer_id", None)
                    st.success(f"Referrer “{deleting_referrer['name']}” was deleted.")
                    st.rerun()

        editing_referrer_id = st.session_state.get("editing_referrer_id")
        editing_referrer = next(
            (referrer for referrer in refs if referrer["id"] == editing_referrer_id),
            None,
        )
        if editing_referrer:
            referrer_id = editing_referrer["id"]
            st.subheader("Edit Referrer Details")
            with st.form(
                f"edit_referrer_form_{referrer_id}",
                clear_on_submit=True,
            ):
                name = st.text_input(
                    "Referrer / chamber name",
                    value=editing_referrer["name"],
                    key=f"edit_referrer_name_{referrer_id}",
                )
                referrer_type = st.radio(
                    "Referrer type",
                    ("Doctor", "3rd party"),
                    index=("Doctor", "3rd party").index(editing_referrer["referrer_type"]),
                    horizontal=True,
                    key=f"edit_referrer_type_{referrer_id}",
                )
                phone = st.text_input(
                    "Contact number",
                    value=editing_referrer["phone"],
                    key=f"edit_referrer_phone_{referrer_id}",
                )
                referrer_status = st.selectbox(
                    "Referrer status",
                    ("Active", "Inactive"),
                    index=0 if editing_referrer["active"] else 1,
                    key=f"edit_referrer_active_{referrer_id}",
                    help="Inactive referrers remain in history but cannot be selected for new invoices.",
                )
                active = referrer_status == "Active"
                commission_type = editing_referrer["commission_type"]
                rate = float(editing_referrer["commission_percent"])
                commission_amount = float(editing_referrer["commission_amount"])
                if staff["role"] == "Owner":
                    commission_type = st.radio(
                        "Commission calculation",
                        COMMISSION_TYPES,
                        index=COMMISSION_TYPES.index(commission_type),
                        horizontal=True,
                        key=f"edit_referrer_commission_type_{referrer_id}",
                        help="Percentage is calculated from test subtotal; fixed amount is paid per invoice.",
                    )
                    rate = st.number_input(
                        "Default commission rate (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=rate,
                        step=0.5,
                        key=f"edit_referrer_commission_{referrer_id}",
                        help="Used when Percentage is selected.",
                    )
                    commission_amount = st.number_input(
                        "Default commission amount per invoice (৳)",
                        min_value=0.0,
                        value=commission_amount,
                        step=50.0,
                        key=f"edit_referrer_commission_amount_{referrer_id}",
                        help="Used when Fixed amount is selected.",
                    )
                save_clicked = st.form_submit_button("Save referrer changes", type="primary")
            if save_clicked:
                normalized_name = name.strip()
                if not normalized_name:
                    st.error("Enter a referrer name.")
                else:
                    duplicate = db_one(
                        """SELECT id FROM referrers
                           WHERE lower(name) = lower(?) AND id != ?""",
                        (normalized_name, referrer_id),
                    )
                    if duplicate:
                        st.error("Another referrer already uses that name.")
                    else:
                        before = (
                            f"name={editing_referrer['name']}; "
                            f"type={editing_referrer['referrer_type']}; "
                            f"phone={editing_referrer['phone']}; "
                            f"active={int(editing_referrer['active'])}"
                        )
                        after = (
                            f"name={normalized_name}; type={referrer_type}; "
                            f"phone={phone.strip()}; active={int(active)}"
                        )
                        with database() as connection:
                            if staff["role"] == "Owner":
                                before += (
                                    f"; commission_type={editing_referrer['commission_type']}; "
                                    f"commission_percent={editing_referrer['commission_percent']}; "
                                    f"commission_amount={editing_referrer['commission_amount']}"
                                )
                                after += (
                                    f"; commission_type={commission_type}; "
                                    f"commission_percent={rate}; commission_amount={commission_amount}"
                                )
                                connection.execute(
                                    """UPDATE referrers SET name = ?, referrer_type = ?,
                                       phone = ?, commission_percent = ?, commission_type = ?,
                                       commission_amount = ?, active = ? WHERE id = ?""",
                                    (
                                        normalized_name,
                                        referrer_type,
                                        phone.strip(),
                                        rate,
                                        commission_type,
                                        commission_amount,
                                        int(active),
                                        referrer_id,
                                    ),
                                )
                            else:
                                connection.execute(
                                    """UPDATE referrers SET name = ?, referrer_type = ?,
                                       phone = ?, active = ? WHERE id = ?""",
                                    (normalized_name, referrer_type, phone.strip(), int(active), referrer_id),
                                )
                            audit(
                                connection,
                                staff["id"],
                                "Referrer updated",
                                "referrer",
                                referrer_id,
                                before,
                                after,
                            )
                        st.session_state.pop("editing_referrer_id", None)
                        st.success("Referrer changes saved.")
                        st.rerun()
            if st.button("Cancel edit", key=f"cancel_edit_referrer_{referrer_id}"):
                st.session_state.pop("editing_referrer_id", None)
                st.rerun()
        else:
            st.subheader("Add referrer")
            with st.form("new_referrer", clear_on_submit=True):
                name = st.text_input("Referrer / chamber name")
                referrer_type = st.radio("Referrer type", ("Doctor", "3rd party"), horizontal=True)
                phone = st.text_input("Contact number")
                rate = 0.0
                commission_amount = 0.0
                commission_type = "Percentage"
                if staff["role"] == "Owner":
                    commission_type = st.radio(
                        "Commission calculation",
                        COMMISSION_TYPES,
                        horizontal=True,
                        help="Percentage is calculated from test subtotal; fixed amount is paid per invoice.",
                    )
                    rate = st.number_input(
                        "Default commission rate (%)",
                        min_value=0.0,
                        max_value=100.0,
                        value=0.0,
                        step=0.5,
                        help="Used when Percentage is selected.",
                    )
                    commission_amount = st.number_input(
                        "Default commission amount per invoice (৳)",
                        min_value=0.0,
                        value=0.0,
                        step=50.0,
                        help="Used when Fixed amount is selected.",
                    )
                submitted = st.form_submit_button("Add referrer")
            if submitted:
                if not name.strip():
                    st.error("Enter a referrer name.")
                else:
                    try:
                        with database() as connection:
                            cursor = connection.execute(
                                """INSERT INTO referrers(name, referrer_type, phone, commission_percent,
                                                         commission_type, commission_amount)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (
                                    name.strip(),
                                    referrer_type,
                                    phone.strip(),
                                    rate,
                                    commission_type,
                                    commission_amount,
                                ),
                            )
                            audit(
                                connection,
                                staff["id"],
                                "Referrer added",
                                "referrer",
                                cursor.lastrowid,
                                "",
                                f"name={name.strip()}; type={referrer_type}; "
                                f"commission_type={commission_type}; active",
                            )
                        st.success("Referrer added.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("That referrer already exists.")
    with roles_tab:
        st.subheader("Role access overview")
        role_rights = [
            {
                "Role": "Owner",
                "Dashboard": "Owner Dashboard",
                "Modules": "All modules, including Lab Work, user-wise Reports and the tenant Audit Trail",
                "Management": "Manage staff accounts; create, edit and deactivate users; manage catalog and referrers; set and pay commissions",
                "Operations": "Full financial oversight; due-report override; inventory management; collect samples, enter and verify results, authorize reports",
            },
            {
                "Role": "Admin",
                "Dashboard": "Admin Dashboard",
                "Modules": "All operational modules, including Lab Work and the tenant Audit Trail",
                "Management": "Create and manage Receptionist, Cashier and Lab Tech users; manage catalog and referrers",
                "Operations": "Manage inventory; release reports with dues using a reason; collect samples, enter and verify results, authorize reports; no owner-only commission settings",
            },
            {
                "Role": "Receptionist",
                "Dashboard": "Receptionist Dashboard",
                "Modules": "Patient search/registration, invoices, dues, test assignment, report delivery, inventory view and day open/close",
                "Management": "No staff, catalog, referrer or commission administration",
                "Operations": "Front-desk billing/payments; open/close shifts and record cash payouts; release authorized reports only when dues are settled; inventory is view-only",
            },
            {
                "Role": "Cashier",
                "Dashboard": "Receptionist Dashboard",
                "Modules": "Same front-desk modules as Receptionist in this build",
                "Management": "No staff, catalog, referrer or commission administration",
                "Operations": "Front-desk billing/payments; open/close shifts and record cash payouts; release authorized reports only when dues are settled; inventory is view-only",
            },
            {
                "Role": "Lab Tech",
                "Dashboard": "Lab Tech Dashboard",
                "Modules": "Lab Work only, plus dashboard",
                "Management": "No patient billing, staff, catalog, referrer, inventory or cashier-day administration",
                "Operations": "Collect samples; enter and verify results; authorize report versions; cannot release reports to patients",
            },
        ]
        for role in role_rights:
            with st.expander(f"{role['Role']} · {role['Dashboard']}", expanded=role["Role"] == staff["role"]):
                st.markdown(f"**Modules:** {role['Modules']}")
                st.markdown(f"**Management:** {role['Management']}")
                st.markdown(f"**Operations:** {role['Operations']}")
        st.caption(
            "User management and role assignment are managed by an Owner or Admin. "
            "Commission settings and commission payments remain Owner-only."
        )
    if staff["role"] == "Owner":
        commission_tab = tabs[4]
        with commission_tab:
            commissions = db_rows(
                """SELECT ce.id, r.name AS referrer, i.invoice_no, p.full_name, ce.amount,
                          ce.paid_amount, ce.amount - ce.paid_amount AS payable
                   FROM commission_entries ce JOIN referrers r ON r.id = ce.referrer_id
                   JOIN invoices i ON i.id = ce.invoice_id JOIN visits v ON v.id = i.visit_id
                   JOIN patients p ON p.id = v.patient_id WHERE ce.amount > ce.paid_amount
                   ORDER BY ce.id"""
            )
            st.dataframe(commissions, hide_index=True, use_container_width=True)
            if commissions:
                session = current_session()
                if not session:
                    st.warning("Open a cashier day before paying referral commission.")
                else:
                    commission_map = {
                        f"{row['referrer']} · {row['invoice_no']} · Due {money(row['payable'])}": row
                        for row in commissions
                    }
                    selected_commission = dropdown("Commission to pay", list(commission_map))
                    entry = commission_map[selected_commission]
                    with st.form("pay_commission", clear_on_submit=True):
                        amount = st.number_input("Amount paid (৳)", min_value=0.01, max_value=float(entry["payable"]), value=float(entry["payable"]), step=50.0)
                        submitted = st.form_submit_button("Pay commission")
                    if submitted:
                        try:
                            with database() as connection:
                                payable_row = connection.execute(
                                    """SELECT ce.referrer_id, ce.amount - ce.paid_amount AS payable,
                                              r.name AS referrer
                                       FROM commission_entries ce
                                       JOIN referrers r ON r.id = ce.referrer_id
                                       WHERE ce.id = ?""",
                                    (entry["id"],),
                                ).fetchone()
                                if payable_row is None or amount <= 0 or amount > payable_row["payable"] + 0.005:
                                    raise ValueError("The commission amount exceeds the remaining payable.")
                                paid_at = now()
                                connection.execute(
                                    "UPDATE commission_entries SET paid_amount = paid_amount + ? WHERE id = ?",
                                    (amount, entry["id"]),
                                )
                                payout_cursor = connection.execute(
                                """INSERT INTO ledger(day_session_id, direction, amount, method, entry_type, source_id,
                                                      description, created_by, created_at)
                                   VALUES (?, 'out', ?, 'Cash', 'Commission', ?, ?, ?, ?)""",
                                    (
                                        session["id"],
                                        amount,
                                        entry["id"],
                                        f"Referral commission: {payable_row['referrer']}",
                                        staff["id"],
                                        paid_at,
                                    ),
                                )
                                post_journal_entry(
                                    connection,
                                    paid_at[:10],
                                    f"Commission paid · {payable_row['referrer']}",
                                    [
                                        {
                                            "account_key": "referrer_payable",
                                            "debit": amount,
                                            "party_type": "Referrer",
                                            "party_id": payable_row["referrer_id"],
                                            "description": payable_row["referrer"],
                                        },
                                        {
                                            "account_key": "cash_cash",
                                            "credit": amount,
                                            "description": payable_row["referrer"],
                                        },
                                    ],
                                    created_by=staff["id"],
                                    source_type="Commission paid",
                                    source_key=f"commission-payout:{payout_cursor.lastrowid}",
                                    source_id=entry["id"],
                                )
                                audit(connection, staff["id"], "Commission paid", "commission", entry["id"], "", f"amount={amount:.2f}")
                            st.success("Commission payment recorded.")
                            st.rerun()
                        except (ValueError, sqlite3.Error) as error:
                            st.error(str(error) or "Commission payment could not be recorded.")
            else:
                st.caption("No unpaid referral commissions.")


def database_management(staff):
    if staff["role"] not in ("Owner", "Admin"):
        st.warning("Only an Owner or Admin can manage the referrer database.")
        return

    st.title("Database Management")
    st.caption("Merge duplicate referrers without losing invoice and commission history.")
    referrers = db_rows(
        "SELECT * FROM referrers ORDER BY lower(name), name"
    )
    options = {f"{row['name']} · {row['referrer_type']} · ID {row['id']}": row for row in referrers}

    st.subheader("Merge duplicate referrers")
    exact_groups = {}
    for referrer in referrers:
        normalized = " ".join(referrer["name"].lower().split())
        exact_groups.setdefault(normalized, []).append(referrer)
    suggestions = {name: rows for name, rows in exact_groups.items() if len(rows) > 1}
    if suggestions:
        for normalized_name, rows in suggestions.items():
            st.caption(
                f"Possible duplicate: {', '.join(row['name'] for row in rows)}"
            )

    if len(referrers) < 2:
        st.info("Add at least two referrers before merging duplicates.")
    else:
        source_label = st.selectbox(
            "Referrer to merge (will be removed)",
            list(options),
            key="database_referrer_merge_source",
        )
        target_label = st.selectbox(
            "Keep this referrer",
            list(options),
            key="database_referrer_merge_target",
        )
        if st.button("Merge referrers", type="primary", key="merge_referrers"):
            source = options[source_label]
            target = options[target_label]
            if source["id"] == target["id"]:
                st.error("Choose two different referrers.")
            else:
                source_snapshot = dict(source)
                with database() as connection:
                    cursor = connection.execute(
                        """INSERT INTO referrer_merges(
                               source_id, source_snapshot, target_id, merged_by, merged_at
                           ) VALUES (?, ?, ?, ?, ?)""",
                        (
                            source["id"],
                            json.dumps(source_snapshot, ensure_ascii=False),
                            target["id"],
                            staff["id"],
                            now(),
                        ),
                    )
                    merge_id = cursor.lastrowid
                    for table_name, column_name in (
                        ("invoices", "referrer_id"),
                        ("invoices", "ordered_by_referrer_id"),
                        ("commission_entries", "referrer_id"),
                    ):
                        records = connection.execute(
                            f"SELECT id FROM {table_name} WHERE {column_name} = ?",
                            (source["id"],),
                        ).fetchall()
                        for record in records:
                            connection.execute(
                                """INSERT INTO referrer_merge_records(
                                       merge_id, table_name, column_name, record_id
                                   ) VALUES (?, ?, ?, ?)""",
                                (merge_id, table_name, column_name, record["id"]),
                            )
                        connection.execute(
                            f"UPDATE {table_name} SET {column_name} = ? WHERE {column_name} = ?",
                            (target["id"], source["id"]),
                        )
                    connection.execute("DELETE FROM referrers WHERE id = ?", (source["id"],))
                    audit(
                        connection,
                        staff["id"],
                        "Referrers merged",
                        "referrer",
                        target["id"],
                        f"{source['name']} (ID {source['id']})",
                        f"{target['name']} (ID {target['id']})",
                    )
                st.success(f"Merged {source['name']} into {target['name']}.")
                st.rerun()

    st.divider()
    st.subheader("Recent referrer merges")
    merges = db_rows(
        """SELECT m.*, source.name AS current_source_name, target.name AS target_name
           FROM referrer_merges m
           LEFT JOIN referrers source ON source.id = m.source_id
           JOIN referrers target ON target.id = m.target_id
           ORDER BY m.id DESC LIMIT 50"""
    )
    if not merges:
        st.info("No referrer merges have been made.")
    for merge in merges:
        snapshot = json.loads(merge["source_snapshot"])
        status = "Undone" if merge["undone_at"] else "Merged"
        st.markdown(
            f"**{snapshot['name']}** → **{merge['target_name']}** · "
            f"{status} · {merge['merged_at']}"
        )
        if (
            not merge["undone_at"]
            and st.session_state.get("tenant_dev_actor")
            and st.button(
                "Undo merge (Dev only)",
                key=f"undo_referrer_merge_{merge['id']}",
                type="secondary",
            )
        ):
            snapshot = json.loads(merge["source_snapshot"])
            with database() as connection:
                existing = connection.execute(
                    "SELECT id FROM referrers WHERE id = ? OR lower(name) = lower(?)",
                    (snapshot["id"], snapshot["name"]),
                ).fetchone()
                if existing:
                    st.error(
                        "This merge cannot be undone because the source ID or name is now in use."
                    )
                else:
                    connection.execute(
                        """INSERT INTO referrers(
                               id, name, referrer_type, phone, commission_percent,
                               commission_type, commission_amount, active
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            snapshot["id"],
                            snapshot["name"],
                            snapshot["referrer_type"],
                            snapshot["phone"],
                            snapshot["commission_percent"],
                            snapshot["commission_type"],
                            snapshot["commission_amount"],
                            snapshot["active"],
                        ),
                    )
                    records = connection.execute(
                        """SELECT table_name, column_name, record_id
                           FROM referrer_merge_records WHERE merge_id = ?""",
                        (merge["id"],),
                    ).fetchall()
                    allowed_tables = {
                        ("invoices", "referrer_id"),
                        ("invoices", "ordered_by_referrer_id"),
                        ("commission_entries", "referrer_id"),
                    }
                    for record in records:
                        reference = (record["table_name"], record["column_name"])
                        if reference in allowed_tables:
                            table_name, column_name = reference
                            current = connection.execute(
                                f"SELECT {column_name} FROM {table_name} WHERE id = ?",
                                (record["record_id"],),
                            ).fetchone()
                            if current and current[column_name] == merge["target_id"]:
                                connection.execute(
                                    f"UPDATE {table_name} SET {column_name} = ? WHERE id = ?",
                                    (snapshot["id"], record["record_id"]),
                                )
                    connection.execute(
                        """UPDATE referrer_merges SET undone_at = ?, undone_by = ?
                           WHERE id = ?""",
                        (now(), staff["id"], merge["id"]),
                    )
                    audit(
                        connection,
                        staff["id"],
                        "Referrer merge undone",
                        "referrer",
                        snapshot["id"],
                        f"Merged into referrer ID {merge['target_id']}",
                        f"Restored {snapshot['name']}",
                    )
                st.success(f"Restored {snapshot['name']} and its recorded history.")
                st.rerun()


def report_date_filter(key_prefix):
    today = datetime.now().astimezone().date()
    first_of_month = today.replace(day=1)
    start_column, end_column = st.columns(2)
    with start_column:
        start_date = st.date_input(
            "From",
            value=first_of_month,
            key=f"{key_prefix}_start_date",
        )
    with end_column:
        end_date = st.date_input(
            "To",
            value=today,
            key=f"{key_prefix}_end_date",
        )
    if start_date > end_date:
        st.error("The start date must be on or before the end date.")
        return None
    return start_date.isoformat(), end_date.isoformat()


def report_download(rows, label, key):
    if not rows:
        st.info("No records match this report and date range.")
        return
    st.dataframe(rows, hide_index=True, use_container_width=True)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    st.download_button(
        label,
        output.getvalue().encode("utf-8-sig"),
        file_name=f"{key}.csv",
        mime="text/csv",
        key=f"download_{key}",
    )


def user_reports_screen(staff):
    if staff["role"] != "Owner":
        st.error("Only an Owner can access user-wise reports.")
        return
    st.title("User-Wise Reports")
    st.caption("Staff activity and financial activity for the selected period.")
    st.info(
        "These reports show billed value and recorded cash activity, not net profit. "
        "The current system does not record diagnostic test costs, payroll, or full overhead allocation."
    )
    date_range = report_date_filter("user_reports")
    if date_range is None:
        return
    start_date, end_date = date_range
    performance_tab, tests_tab, commission_tab, financial_tab = st.tabs(
        ["User performance", "Tests by user", "Referrer commissions", "Financial activity"]
    )

    with performance_tab:
        rows = db_rows(
            """WITH invoice_stats AS (
                   SELECT created_by AS staff_id, COUNT(*) AS invoice_count,
                          SUM(net) AS billed_net
                   FROM invoices
                   WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY created_by
               ),
               test_stats AS (
                   SELECT i.created_by AS staff_id, COUNT(*) AS billed_tests,
                          SUM(CASE WHEN il.status = 'Cancelled' THEN 1 ELSE 0 END)
                              AS canceled_tests
                   FROM invoice_lines il JOIN invoices i ON i.id = il.invoice_id
                   WHERE substr(i.created_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY i.created_by
               ),
               payment_stats AS (
                   SELECT received_by AS staff_id, COUNT(*) AS payment_count,
                          SUM(amount) AS payments_received
                   FROM payments
                   WHERE substr(received_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY received_by
               ),
               refund_stats AS (
                   SELECT paid_by AS staff_id, COUNT(*) AS refund_count,
                          SUM(amount) AS refunds_paid
                   FROM refunds
                   WHERE substr(paid_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY paid_by
               ),
               audit_stats AS (
                   SELECT staff_id, COUNT(*) AS audited_actions,
                          SUM(CASE WHEN action = 'Test reassigned' THEN 1 ELSE 0 END)
                              AS test_reassignments,
                          SUM(CASE WHEN action = 'Sample collected' THEN 1 ELSE 0 END)
                              AS samples_collected,
                          SUM(CASE WHEN action = 'Lab result entered' THEN 1 ELSE 0 END)
                              AS results_entered,
                          SUM(CASE WHEN action = 'Result verified and report authorized'
                                   THEN 1 ELSE 0 END) AS reports_authorized,
                          SUM(CASE WHEN action = 'Report handed over' THEN 1 ELSE 0 END)
                              AS reports_delivered
                   FROM audit_log
                   WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY staff_id
               )
               SELECT s.display_name AS staff_name, s.username, s.role,
                      CASE WHEN s.active THEN 'Active' ELSE 'Disabled' END AS account_status,
                      COALESCE(i.invoice_count, 0) AS invoices_created,
                      ROUND(COALESCE(i.billed_net, 0), 2) AS billed_net,
                      COALESCE(t.billed_tests, 0) AS tests_billed,
                      COALESCE(t.canceled_tests, 0) AS tests_canceled,
                      COALESCE(p.payment_count, 0) AS payments_received_count,
                      ROUND(COALESCE(p.payments_received, 0), 2) AS payments_received,
                      COALESCE(r.refund_count, 0) AS refunds_paid_count,
                      ROUND(COALESCE(r.refunds_paid, 0), 2) AS refunds_paid,
                      COALESCE(a.audited_actions, 0) AS audited_actions,
                      COALESCE(a.test_reassignments, 0) AS tests_reassigned,
                      COALESCE(a.samples_collected, 0) AS samples_collected,
                      COALESCE(a.results_entered, 0) AS results_entered,
                      COALESCE(a.reports_authorized, 0) AS reports_authorized,
                      COALESCE(a.reports_delivered, 0) AS reports_delivered
               FROM staff s
               LEFT JOIN invoice_stats i ON i.staff_id = s.id
               LEFT JOIN test_stats t ON t.staff_id = s.id
               LEFT JOIN payment_stats p ON p.staff_id = s.id
               LEFT JOIN refund_stats r ON r.staff_id = s.id
               LEFT JOIN audit_stats a ON a.staff_id = s.id
               ORDER BY s.display_name, s.username""",
            (
                start_date, end_date, start_date, end_date, start_date, end_date,
                start_date, end_date, start_date, end_date,
            ),
        )
        report_download(rows, "Download user performance CSV", "user-performance")
        st.caption(
            "Activity counts for collection, laboratory, and delivery actions come from recorded "
            "audit events. Events created before those actions were logged cannot be attributed."
        )

    with tests_tab:
        rows = db_rows(
            """SELECT s.display_name AS billed_by, s.username, il.department, il.test_name,
                      COUNT(*) AS test_count,
                      SUM(CASE WHEN il.status = 'Cancelled' THEN 1 ELSE 0 END)
                          AS canceled_count,
                      ROUND(SUM(CASE WHEN il.status != 'Cancelled'
                                     THEN il.unit_price ELSE 0 END), 2) AS active_billed_value
               FROM invoice_lines il
               JOIN invoices i ON i.id = il.invoice_id
               LEFT JOIN staff s ON s.id = i.created_by
               WHERE substr(i.created_at, 1, 10) BETWEEN ? AND ?
               GROUP BY s.id, s.display_name, s.username, il.department, il.test_name
               ORDER BY test_count DESC, billed_by, il.department, il.test_name""",
            (start_date, end_date),
        )
        report_download(rows, "Download test-by-user CSV", "tests-by-user")
        st.caption(
            "“Billed by” identifies the invoice creator. It does not imply that person "
            "performed the laboratory test."
        )

    with commission_tab:
        rows = db_rows(
            """WITH accrued AS (
                   SELECT ce.referrer_id, COUNT(*) AS invoices_with_commission,
                          SUM(ce.amount) AS accrued_in_period
                   FROM commission_entries ce
                   JOIN invoices i ON i.id = ce.invoice_id
                   WHERE substr(i.created_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY ce.referrer_id
               ),
               paid_in_period AS (
                   SELECT ce.referrer_id, SUM(l.amount) AS paid_in_period
                   FROM ledger l
                   JOIN commission_entries ce ON ce.id = l.source_id
                   WHERE l.entry_type = 'Commission' AND l.direction = 'out'
                     AND substr(l.created_at, 1, 10) BETWEEN ? AND ?
                   GROUP BY ce.referrer_id
               ),
               current_balance AS (
                   SELECT referrer_id, SUM(amount) AS accrued_total,
                          SUM(paid_amount) AS paid_total,
                          SUM(amount - paid_amount) AS outstanding
                   FROM commission_entries
                   GROUP BY referrer_id
               )
               SELECT r.name AS referrer, r.referrer_type,
                      COALESCE(a.invoices_with_commission, 0) AS invoices_with_commission,
                      ROUND(COALESCE(a.accrued_in_period, 0), 2) AS accrued_in_period,
                      ROUND(COALESCE(p.paid_in_period, 0), 2) AS paid_in_period,
                      ROUND(COALESCE(b.accrued_total, 0), 2) AS accrued_all_time,
                      ROUND(COALESCE(b.paid_total, 0), 2) AS paid_all_time,
                      ROUND(COALESCE(b.outstanding, 0), 2) AS currently_outstanding
               FROM referrers r
               LEFT JOIN accrued a ON a.referrer_id = r.id
               LEFT JOIN paid_in_period p ON p.referrer_id = r.id
               LEFT JOIN current_balance b ON b.referrer_id = r.id
               WHERE a.referrer_id IS NOT NULL OR p.referrer_id IS NOT NULL
                     OR b.referrer_id IS NOT NULL
               ORDER BY currently_outstanding DESC, r.name""",
            (start_date, end_date, start_date, end_date),
        )
        report_download(rows, "Download commission report CSV", "referrer-commissions")
        st.caption(
            "Commissions belong to referrers, not staff. Period accrual follows invoice date; "
            "period payments use commission ledger dates; outstanding is the current balance."
        )

    with financial_tab:
        summary = db_one(
            """SELECT
                 (SELECT COALESCE(SUM(net), 0) FROM invoices
                  WHERE substr(created_at, 1, 10) BETWEEN ? AND ?) AS net_billed,
                 (SELECT COALESCE(SUM(discount), 0) FROM invoices
                  WHERE substr(created_at, 1, 10) BETWEEN ? AND ?) AS discounts,
                 (SELECT COALESCE(SUM(amount), 0) FROM payments
                  WHERE substr(received_at, 1, 10) BETWEEN ? AND ?) AS payments_received,
                 (SELECT COALESCE(SUM(amount), 0) FROM refunds
                  WHERE substr(paid_at, 1, 10) BETWEEN ? AND ?) AS refunds_paid,
                 (SELECT COALESCE(SUM(amount), 0) FROM ledger
                  WHERE direction = 'out' AND entry_type = 'Expense'
                    AND substr(created_at, 1, 10) BETWEEN ? AND ?) AS recorded_expenses,
                 (SELECT COALESCE(SUM(amount), 0) FROM ledger
                  WHERE direction = 'out' AND entry_type = 'Commission'
                    AND substr(created_at, 1, 10) BETWEEN ? AND ?) AS commissions_paid""",
            (
                start_date, end_date, start_date, end_date, start_date, end_date,
                start_date, end_date, start_date, end_date, start_date, end_date,
            ),
        )
        financial_rows = [
            {"Measure": label, "Amount": money(summary[field])}
            for label, field in (
                ("Net billed", "net_billed"),
                ("Discounts", "discounts"),
                ("Payments received", "payments_received"),
                ("Patient refunds paid", "refunds_paid"),
                ("Recorded cash expenses", "recorded_expenses"),
                ("Referral commissions paid", "commissions_paid"),
            )
        ]
        report_download(
            financial_rows,
            "Download financial activity CSV",
            "financial-activity",
        )
        st.caption(
            "This is an operational financial summary, not a profit-and-loss statement. "
            "It excludes costs not recorded in MedScope and does not apply accounting-period "
            "accrual rules."
        )


def audit_screen(staff):
    if staff["role"] not in ("Owner", "Admin"):
        st.error("Only an Owner or Admin can access the tenant audit trail.")
        return
    st.title("Audit Trail")
    st.caption("Tenant-level record of actions recorded by MedScope.")
    date_range = report_date_filter("audit")
    if date_range is None:
        return
    start_date, end_date = date_range
    staff_rows = db_rows(
        "SELECT id, username, display_name FROM staff ORDER BY display_name, username"
    )
    staff_options = {"All accounts": None}
    staff_options.update(
        {
            f"{row['display_name']} · {row['username']}": row["id"]
            for row in staff_rows
        }
    )
    filter_columns = st.columns([1.3, 1.3, 2])
    with filter_columns[0]:
        selected_staff = st.selectbox(
            "User",
            list(staff_options),
            key="audit_user_filter",
        )
    with filter_columns[1]:
        entity_types = db_rows(
            """SELECT DISTINCT entity_type FROM audit_log
               WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
               ORDER BY entity_type""",
            (start_date, end_date),
        )
        entity_options = ["All entities"] + [row["entity_type"] for row in entity_types]
        selected_entity = st.selectbox(
            "Record type",
            entity_options,
            key="audit_entity_filter",
        )
    with filter_columns[2]:
        search_text = st.text_input(
            "Search action, record ID or details",
            key="audit_search_text",
        ).strip()
    action_options = db_rows(
        """SELECT DISTINCT action FROM audit_log
           WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
           ORDER BY action""",
        (start_date, end_date),
    )
    selected_action = st.selectbox(
        "Action",
        ["All actions"] + [row["action"] for row in action_options],
        key="audit_action_filter",
    )
    conditions = ["substr(a.created_at, 1, 10) BETWEEN ? AND ?"]
    params = [start_date, end_date]
    if staff_options[selected_staff] is not None:
        conditions.append("a.staff_id = ?")
        params.append(staff_options[selected_staff])
    if selected_entity != "All entities":
        conditions.append("a.entity_type = ?")
        params.append(selected_entity)
    if selected_action != "All actions":
        conditions.append("a.action = ?")
        params.append(selected_action)
    if search_text:
        pattern = f"%{search_text}%"
        conditions.append(
            """(a.action LIKE ? OR a.entity_type LIKE ? OR a.entity_id LIKE ?
               OR a.before_value LIKE ? OR a.after_value LIKE ?
               OR s.username LIKE ? OR s.display_name LIKE ? OR a.acting_role LIKE ?)"""
        )
        params.extend([pattern] * 8)
    where_clause = " AND ".join(conditions)
    total = db_one(
        f"""SELECT COUNT(*) AS total FROM audit_log a
             LEFT JOIN staff s ON s.id = a.staff_id WHERE {where_clause}""",
        params,
    )["total"]
    rows = db_rows(
        f"""SELECT a.created_at AS timestamp,
                   COALESCE(s.display_name, 'System / Platform Dev') AS user,
                   COALESCE(s.username, '') AS username,
                   a.acting_role AS role, a.action, a.entity_type AS record_type,
                   a.entity_id AS record_id, a.before_value, a.after_value
            FROM audit_log a LEFT JOIN staff s ON s.id = a.staff_id
            WHERE {where_clause}
            ORDER BY a.id DESC LIMIT 2000""",
        params,
    )
    st.caption(f"{total:,} matching event(s); showing up to the latest 2,000.")
    if rows:
        report_download(rows, "Download filtered audit CSV", "audit-events")
    else:
        st.info("No audit events match the selected filters.")


def patient_search():
    st.title("Find Patient")
    search = st.text_input("Search by patient ID, name or contact")
    if not search.strip():
        st.caption("Enter a patient ID, name or phone number.")
        return
    term = f"%{search.strip()}%"
    patients = db_rows(
        """SELECT p.id, p.patient_code, p.full_name, p.sex, p.age, p.phone, p.address, p.created_at,
                  COUNT(v.id) AS visits
           FROM patients p LEFT JOIN visits v ON v.patient_id = p.id
           WHERE p.patient_code LIKE ? OR p.full_name LIKE ? OR p.phone LIKE ?
           GROUP BY p.id ORDER BY p.id DESC LIMIT 50""",
        (term, term, term),
    )
    if not patients:
        st.info("No matching patients.")
        return
    patient_options = {f"{p['patient_code']} · {p['full_name']} · {p['phone']}": p for p in patients}
    selected = dropdown("Patient record", list(patient_options))
    patient = patient_options[selected]
    st.write(f"**{patient['full_name']}** · {patient['sex']} · Age {patient['age'] or '—'}")
    st.write(f"Contact: {patient['phone']} · Address: {patient['address'] or '—'} · Visits: {patient['visits']}")
    visits = db_rows(
        """SELECT i.invoice_no, i.created_at, i.net, i.paid, i.due, i.refund_due, i.status
           FROM invoices i JOIN visits v ON v.id = i.visit_id
           WHERE v.patient_id = ? ORDER BY i.id DESC""",
        (patient["id"],),
    )
    if visits:
        st.subheader("Visit & billing history")
        st.dataframe(visits, hide_index=True, use_container_width=True)


def dev_portal(developer):
    destination = st.session_state.get("dev_access_destination")
    st.title("MedScope Dev module" if destination == "Dev Module" else "Dev access")
    if st.button("Sign out of Dev", key="sign_out_dev"):
        st.session_state.pop("platform_dev", None)
        st.session_state.pop("platform_dev_authenticated_at", None)
        st.session_state.pop("staff", None)
        st.session_state.pop("tenant_id", None)
        st.session_state.pop("tenant_db_path", None)
        st.session_state.pop("dev_access_destination", None)
        st.rerun()

    if destination is None:
        st.success(f"Authenticated as {developer['name']}.")
        st.caption("Choose how you want to continue.")
        dev_column, tenant_column = st.columns(2, gap="large")
        with dev_column:
            st.subheader("Dev Module")
            st.write("Manage diagnostic centers, tenant accounts, and platform audit.")
            if st.button("Dev Login", type="primary", key="open_dev_module"):
                st.session_state["dev_access_destination"] = "Dev Module"
                st.rerun()
        with tenant_column:
            st.subheader("Tenant access")
            st.write("Select a diagnostic center to enter with Dev access.")
            tenants = platform_tenants()
            if not tenants:
                st.info("No diagnostic centers are available.")
            else:
                tenant_options = {
                    f"{tenant['name']} · {tenant['slug']} · "
                    f"{'Active' if tenant['active'] else 'Disabled'}": tenant
                    for tenant in tenants
                }
                selected_label = st.selectbox(
                    "Diagnostic center",
                    list(tenant_options),
                    key="dev_tenant_access_selection",
                )
                tenant = tenant_options[selected_label]
                if st.button(
                    "Sign in",
                    type="primary",
                    key="dev_tenant_access_sign_in",
                ):
                    tenant_path = tenant_database_path(tenant["id"])
                    if not tenant_path.is_file():
                        st.error(
                            f"The database for {tenant['name']} is missing. "
                            "Restore it from backup before continuing."
                        )
                    else:
                        initialize_database(tenant_path)
                        with database(tenant_path) as connection:
                            owner = connection.execute(
                                """SELECT id, username, display_name
                                   FROM staff
                                   WHERE role = 'Owner' AND active = 1
                                   ORDER BY display_name, username
                                   LIMIT 1"""
                            ).fetchone()
                        if owner is None:
                            st.error(
                                "This tenant has no active Owner / Super Admin account. "
                                "Create or reactivate one in the Dev Module first."
                            )
                        else:
                            st.session_state["tenant_id"] = tenant["id"]
                            st.session_state["tenant_db_path"] = str(tenant_path)
                            st.session_state["staff"] = {
                                "id": owner["id"],
                                "name": owner["display_name"],
                                "username": owner["username"],
                                "role": "Owner",
                            }
                            st.session_state["tenant_dev_actor"] = developer["username"]
                            st.session_state["dev_access_destination"] = "Dev Module"
                            st.session_state["navigation_page"] = "Dashboard"
                            with platform_database() as connection:
                                platform_audit(
                                    connection,
                                    developer["id"],
                                    "Platform Dev opened tenant as Dev",
                                    tenant["id"],
                                    f"owner_context={owner['username']}",
                                )
                            st.rerun()
        return

    if destination != "Dev Module":
        st.error("The selected Dev destination is invalid.")
        st.session_state.pop("dev_access_destination", None)
        st.rerun()

    st.caption("Platform administration · Tenant governance · Owner / Super Admin provisioning")
    tenant_tab, audit_tab = st.tabs(["Tenant management", "Platform audit"])
    tenants = platform_tenants()
    with tenant_tab:
        st.subheader("Diagnostic centers")
        create_tenant_container = st.container()
        if tenants:
            st.dataframe(
                [
                    {
                        "Tenant": tenant["name"],
                        "Tenant code": tenant["slug"],
                        "Status": "Active" if tenant["active"] else "Disabled",
                        "Created": tenant["created_at"],
                    }
                    for tenant in tenants
                ],
                hide_index=True,
                use_container_width=True,
            )
            tenant_options = {
                f"{tenant['name']} · {tenant['slug']} · "
                f"{'Active' if tenant['active'] else 'Disabled'}": tenant
                for tenant in tenants
            }
            selected_label = st.selectbox(
                "Tenant to manage",
                list(tenant_options),
                help="Type a tenant name or code to search.",
                key="dev_tenant_selection",
            )
            tenant = tenant_options[selected_label]
            with st.expander("Edit tenant details", expanded=False):
                with st.form(
                    f"edit_tenant_{tenant['id']}",
                    clear_on_submit=True,
                ):
                    updated_tenant_name = st.text_input(
                        "Diagnostic center name",
                        value=tenant["name"],
                        key=f"edit_tenant_name_{tenant['id']}",
                    )
                    edit_tenant_submitted = st.form_submit_button(
                        "Save tenant details",
                        type="primary",
                    )
                if edit_tenant_submitted:
                    updated_tenant_name = updated_tenant_name.strip()
                    if not updated_tenant_name:
                        st.error("Enter a diagnostic center name.")
                    elif updated_tenant_name != tenant["name"]:
                        with platform_database() as connection:
                            connection.execute(
                                "UPDATE tenants SET name = ? WHERE id = ?",
                                (updated_tenant_name, tenant["id"]),
                            )
                            platform_audit(
                                connection,
                                developer["id"],
                                "Tenant details updated",
                                tenant["id"],
                                f"name: {tenant['name']} -> {updated_tenant_name}",
                            )
                        st.success("Tenant details updated.")
                        st.rerun()
                    else:
                        st.info("No tenant details were changed.")

            columns = st.columns(2)
            desired_active = not bool(tenant["active"])
            if columns[0].button(
                "Enable tenant" if desired_active else "Disable tenant",
                type="primary" if desired_active else "secondary",
                key=f"toggle_tenant_{tenant['id']}",
            ):
                with platform_database() as connection:
                    connection.execute(
                        "UPDATE tenants SET active = ? WHERE id = ?",
                        (int(desired_active), tenant["id"]),
                    )
                    platform_audit(
                        connection,
                        developer["id"],
                        "Tenant enabled" if desired_active else "Tenant disabled",
                        tenant["id"],
                        tenant["slug"],
                    )
                st.success(
                    "Tenant enabled. Tenant users can sign in."
                    if desired_active
                    else "Tenant disabled. All tenant sign-ins are blocked."
                )
                st.rerun()

            tenant_path = tenant_database_path(tenant["id"])
            if not tenant_path.is_file():
                st.error(
                    f"The database for {tenant['name']} is missing. Restore it from backup; "
                    "the Dev module will not create an empty replacement."
                )
                st.stop()
            initialize_database(tenant_path)
            with database(tenant_path) as connection:
                staff_accounts = [
                    dict(row)
                    for row in connection.execute(
                        """SELECT id, username, display_name, role, active, locked
                           FROM staff ORDER BY role, display_name"""
                    ).fetchall()
                ]
            owners = [account for account in staff_accounts if account["role"] == "Owner"]

            with st.expander("Create an Owner / Super Admin account", expanded=False):
                st.caption("Owner / Super Admin is the tenant's full-access role.")
                with st.form(
                    f"create_tenant_owner_{tenant['id']}",
                    clear_on_submit=True,
                ):
                    owner_name = st.text_input(
                        "Owner / Super Admin name",
                        key=f"new_owner_name_{tenant['id']}",
                    )
                    owner_username = st.text_input(
                        "Owner / Super Admin username",
                        key=f"new_owner_username_{tenant['id']}",
                    )
                    owner_pin = st.text_input(
                        "Owner / Super Admin PIN (4–6 digits)",
                        type="password",
                        key=f"new_owner_pin_{tenant['id']}",
                    )
                    submitted = st.form_submit_button(
                        "Create Owner / Super Admin account",
                        type="primary",
                    )
                if submitted:
                    if not owner_name.strip() or not owner_username.strip():
                        st.error("Enter the Owner name and username.")
                    elif not owner_pin.isdigit() or not 4 <= len(owner_pin) <= 6:
                        st.error("The Owner PIN must contain 4–6 digits.")
                    else:
                        try:
                            if staff_username_is_taken(
                                owner_username, tenant["id"]
                            ):
                                raise ValueError(
                                    "Usernames must be unique across diagnostic centers."
                                )
                            with database(tenant_path) as connection:
                                cursor = connection.execute(
                                    """INSERT INTO staff(username, display_name, password_hash,
                                                         role, created_at)
                                       VALUES (?, ?, ?, 'Owner', ?)""",
                                    (
                                        owner_username.strip().lower(),
                                        owner_name.strip(),
                                        password_digest(owner_pin),
                                        now(),
                                    ),
                                )
                                audit(
                                    connection,
                                    None,
                                    "Owner account created by Platform Dev",
                                    "staff",
                                    cursor.lastrowid,
                                    "",
                                    f"{owner_username.strip().lower()}; tenant={tenant['slug']}",
                                    acting_role_override=f"Platform Dev ({developer['username']})",
                                )
                            with platform_database() as connection:
                                platform_audit(
                                    connection,
                                    developer["id"],
                                    "Tenant Owner account created",
                                    tenant["id"],
                                    owner_username.strip().lower(),
                                )
                            st.success(f"Owner account created for {tenant['name']}.")
                            st.rerun()
                        except (ValueError, RuntimeError, sqlite3.Error) as error:
                            st.error(str(error) or "The username could not be verified.")

            st.subheader("Tenant accounts")
            st.caption(
                "All Owner / Super Admin and staff accounts for the selected tenant. "
                "Deleting an account disables sign-in but retains its history."
            )
            st.dataframe(
                [
                    {
                        "Name": account["display_name"],
                        "Username": account["username"],
                        "Role": account["role"],
                        "Status": "Active" if account["active"] else "Disabled",
                        "PIN lock": "Locked" if account["locked"] else "",
                    }
                    for account in staff_accounts
                ],
                hide_index=True,
                use_container_width=True,
            )
            if staff_accounts:
                staff_account_options = {
                    f"{account['display_name']} · {account['username']} · "
                    f"{account['role']} · "
                    f"{'Active' if account['active'] else 'Disabled'}": account
                    for account in staff_accounts
                }
                selected_account_label = st.selectbox(
                    "Account to manage",
                    list(staff_account_options),
                    help="Type a name or username to search.",
                    key=f"dev_manage_account_{tenant['id']}",
                )
                selected_account = staff_account_options[selected_account_label]
                account_actions = st.columns(2)
                if account_actions[0].button(
                    "Edit account",
                    key=f"dev_edit_account_{tenant['id']}_{selected_account['id']}",
                ):
                    st.session_state[f"dev_editing_account_{tenant['id']}"] = (
                        selected_account["id"]
                    )
                    st.session_state.pop(f"dev_deleting_account_{tenant['id']}", None)
                    st.rerun()
                if selected_account["active"] and account_actions[1].button(
                    "Delete account",
                    key=f"dev_delete_account_{tenant['id']}_{selected_account['id']}",
                ):
                    st.session_state[f"dev_deleting_account_{tenant['id']}"] = (
                        selected_account["id"]
                    )
                    st.session_state.pop(f"dev_editing_account_{tenant['id']}", None)
                    st.rerun()

                editing_account_id = st.session_state.get(
                    f"dev_editing_account_{tenant['id']}"
                )
                editing_account = next(
                    (account for account in staff_accounts if account["id"] == editing_account_id),
                    None,
                )
                if editing_account:
                    st.subheader("Edit tenant account")
                    with st.form(
                        f"dev_edit_account_form_{tenant['id']}_{editing_account['id']}",
                        clear_on_submit=True,
                    ):
                        edited_account_name = st.text_input(
                            "Name",
                            value=editing_account["display_name"],
                            key=f"dev_edit_account_name_{tenant['id']}_{editing_account['id']}",
                        )
                        edited_account_username = st.text_input(
                            "Username",
                            value=editing_account["username"],
                            key=f"dev_edit_account_username_{tenant['id']}_{editing_account['id']}",
                        )
                        edited_account_role = st.selectbox(
                            "Role",
                            ROLES,
                            index=ROLES.index(editing_account["role"]),
                            key=f"dev_edit_account_role_{tenant['id']}_{editing_account['id']}",
                        )
                        edited_account_status = st.selectbox(
                            "Account status",
                            ("Active", "Disabled"),
                            index=0 if editing_account["active"] else 1,
                            key=f"dev_edit_account_status_{tenant['id']}_{editing_account['id']}",
                        )
                        new_account_pin = st.text_input(
                            "New PIN (leave blank to keep current)",
                            type="password",
                            key=f"dev_edit_account_pin_{tenant['id']}_{editing_account['id']}",
                        )
                        save_account = st.form_submit_button(
                            "Save account changes",
                            type="primary",
                        )
                    if save_account:
                        normalized_username = edited_account_username.strip().lower()
                        if not edited_account_name.strip() or not normalized_username:
                            st.error("Enter both an account name and username.")
                        elif new_account_pin and (
                            not new_account_pin.isdigit()
                            or not 4 <= len(new_account_pin) <= 6
                        ):
                            st.error("The new PIN must contain 4–6 digits.")
                        else:
                            try:
                                if staff_username_is_taken(
                                    normalized_username,
                                    tenant["id"],
                                    editing_account["id"],
                                ):
                                    raise ValueError(
                                        "Usernames must be unique across diagnostic centers."
                                    )
                                new_active = int(edited_account_status == "Active")
                                with database(tenant_path) as connection:
                                    connection.execute(
                                        """UPDATE staff SET username = ?, display_name = ?,
                                           role = ?, active = ?,
                                           password_hash = CASE WHEN ? = '' THEN password_hash ELSE ? END,
                                           failed_attempts = CASE WHEN ? = '' THEN failed_attempts ELSE 0 END,
                                           locked = CASE WHEN ? = '' THEN locked ELSE 0 END
                                           WHERE id = ?""",
                                        (
                                            normalized_username,
                                            edited_account_name.strip(),
                                            edited_account_role,
                                            new_active,
                                            new_account_pin,
                                            password_digest(new_account_pin) if new_account_pin else "",
                                            new_account_pin,
                                            new_account_pin,
                                            editing_account["id"],
                                        ),
                                    )
                                    audit(
                                        connection,
                                        None,
                                        "Tenant account updated by Platform Dev",
                                        "staff",
                                        editing_account["id"],
                                        f"{editing_account['username']}; "
                                        f"{editing_account['display_name']}; "
                                        f"{editing_account['role']}; "
                                        f"active={editing_account['active']}",
                                        f"{normalized_username}; {edited_account_name.strip()}; "
                                        f"{edited_account_role}; active={new_active}",
                                        acting_role_override=f"Platform Dev ({developer['username']})",
                                    )
                                with platform_database() as connection:
                                    platform_audit(
                                        connection,
                                        developer["id"],
                                        "Tenant account updated",
                                        tenant["id"],
                                        f"{editing_account['username']} -> {normalized_username}; "
                                        f"role={edited_account_role}; active={new_active}",
                                    )
                                st.session_state.pop(f"dev_editing_account_{tenant['id']}", None)
                                st.success("Tenant account updated.")
                                st.rerun()
                            except (ValueError, RuntimeError, sqlite3.Error) as error:
                                st.error(str(error) or "The username could not be verified.")
                    if st.button(
                        "Cancel account edit",
                        key=f"dev_cancel_edit_account_{tenant['id']}_{editing_account['id']}",
                    ):
                        st.session_state.pop(f"dev_editing_account_{tenant['id']}", None)
                        st.rerun()

                deleting_account_id = st.session_state.get(
                    f"dev_deleting_account_{tenant['id']}"
                )
                deleting_account = next(
                    (account for account in staff_accounts if account["id"] == deleting_account_id),
                    None,
                )
                if deleting_account:
                    st.warning(
                        f"Delete “{deleting_account['display_name']}” "
                        f"({deleting_account['username']}, {deleting_account['role']})? "
                        "This disables sign-in but permanently retains the account and its "
                        "linked audit and operational history."
                    )
                    confirm_delete, cancel_delete = st.columns(2)
                    if confirm_delete.button(
                        f"Confirm delete {deleting_account['display_name']}",
                        type="primary",
                        key=f"dev_confirm_delete_account_{tenant['id']}_{deleting_account['id']}",
                    ):
                        with database(tenant_path) as connection:
                            connection.execute(
                                "UPDATE staff SET active = 0 WHERE id = ?",
                                (deleting_account["id"],),
                            )
                            audit(
                                connection,
                                None,
                                "Tenant account soft-deleted by Platform Dev",
                                "staff",
                                deleting_account["id"],
                                f"{deleting_account['username']}; "
                                f"{deleting_account['display_name']}; "
                                f"{deleting_account['role']}; active=1",
                                "active=0; account retained for audit history",
                                acting_role_override=f"Platform Dev ({developer['username']})",
                            )
                        with platform_database() as connection:
                            platform_audit(
                                connection,
                                developer["id"],
                                "Tenant account soft-deleted",
                                tenant["id"],
                                f"{deleting_account['username']}; role={deleting_account['role']}",
                            )
                        st.session_state.pop(f"dev_deleting_account_{tenant['id']}", None)
                        st.success(
                            f"{deleting_account['display_name']}'s account was disabled; "
                            "its history was retained."
                        )
                        st.rerun()
                    if cancel_delete.button(
                        "Cancel",
                        key=f"dev_cancel_delete_account_{tenant['id']}_{deleting_account['id']}",
                    ):
                        st.session_state.pop(f"dev_deleting_account_{tenant['id']}", None)
                        st.rerun()

            if owners:
                active_owners = [owner for owner in owners if owner["active"]]
                if active_owners:
                    owner_options = {
                        f"{owner['display_name']} · {owner['username']}": owner
                        for owner in active_owners
                    }
                    owner_label = st.selectbox(
                        "Owner / Super Admin context for full tenant administration",
                        list(owner_options),
                        key=f"dev_owner_context_{tenant['id']}",
                    )
                    if st.button(
                        "Open tenant as Platform Dev (Owner / Super Admin access)",
                        type="primary",
                        key=f"open_tenant_dev_{tenant['id']}",
                    ):
                        owner = owner_options[owner_label]
                        st.session_state["tenant_id"] = tenant["id"]
                        st.session_state["tenant_db_path"] = str(tenant_path)
                        st.session_state["staff"] = {
                            "id": owner["id"],
                            "name": owner["display_name"],
                            "username": owner["username"],
                            "role": "Owner",
                        }
                        st.session_state["tenant_dev_actor"] = developer["username"]
                        st.session_state["navigation_page"] = "Dashboard"
                        with platform_database() as connection:
                            platform_audit(
                                connection,
                                developer["id"],
                                "Platform Dev opened tenant administration",
                                tenant["id"],
                                f"owner_context={owner['username']}",
                            )
                        st.rerun()
                else:
                    st.warning(
                        "This tenant has no active Owner / Super Admin account. "
                        "Create or reactivate one."
                    )
            else:
                st.warning(
                    "This tenant has no Owner / Super Admin account. "
                    "Create one to begin administration."
                )
        else:
            st.info("No tenants exist yet.")

        with create_tenant_container:
            with st.expander("Create New Tenant", expanded=not tenants):
                with st.form("create_tenant", clear_on_submit=True):
                    tenant_name = st.text_input("Diagnostic center name")
                    tenant_slug = st.text_input(
                        "Tenant code",
                        help="Use lowercase letters, digits and hyphens; this is shown at tenant sign-in.",
                    )
                    first_owner_name = st.text_input("First Owner / Super Admin name")
                    first_owner_username = st.text_input("First Owner / Super Admin username")
                    first_owner_pin = st.text_input(
                        "First Owner / Super Admin PIN (4–6 digits)",
                        type="password",
                    )
                    create_tenant_submitted = st.form_submit_button(
                        "Create tenant and first Owner / Super Admin",
                        type="primary",
                    )
                if create_tenant_submitted:
                    normalized_slug = re.sub(
                        r"[^a-z0-9]+", "-", tenant_slug.strip().lower()
                    ).strip("-")
                    if not tenant_name.strip() or not normalized_slug:
                        st.error("Enter a tenant name and a valid tenant code.")
                    elif not first_owner_name.strip() or not first_owner_username.strip():
                        st.error("Enter the first Owner / Super Admin name and username.")
                    elif not first_owner_pin.isdigit() or not 4 <= len(first_owner_pin) <= 6:
                        st.error("The first Owner / Super Admin PIN must contain 4–6 digits.")
                    else:
                        tenant_id = str(uuid.uuid4())
                        final_path = tenant_database_path(tenant_id)
                        temp_path = TENANT_DATA_DIR / f".{uuid.UUID(tenant_id).hex}.provisioning.db"
                        final_path_created = False
                        try:
                            if final_path.exists():
                                raise RuntimeError(
                                    "The generated tenant storage file already exists."
                                )
                            with platform_database() as connection:
                                if connection.execute(
                                    "SELECT 1 FROM tenants WHERE slug = ?",
                                    (normalized_slug,),
                                ).fetchone():
                                    raise ValueError("That tenant code is already in use.")
                            if staff_username_is_taken(first_owner_username):
                                raise ValueError(
                                    "Usernames must be unique across diagnostic centers."
                                )
                            initialize_database(temp_path, allow_create=True)
                            with database(temp_path) as connection:
                                cursor = connection.execute(
                                    """INSERT INTO staff(username, display_name, password_hash,
                                                         role, created_at)
                                       VALUES (?, ?, ?, 'Owner', ?)""",
                                    (
                                        first_owner_username.strip().lower(),
                                        first_owner_name.strip(),
                                        password_digest(first_owner_pin),
                                        now(),
                                    ),
                                )
                                audit(
                                    connection,
                                    None,
                                    "Initial Owner account created by Platform Dev",
                                    "staff",
                                    cursor.lastrowid,
                                    "",
                                    f"{first_owner_username.strip().lower()}; tenant={normalized_slug}",
                                    acting_role_override=f"Platform Dev ({developer['username']})",
                                )
                            os.replace(temp_path, final_path)
                            final_path_created = True
                            with platform_database() as connection:
                                connection.execute(
                                    """INSERT INTO tenants(id, slug, name, active, created_at, created_by)
                                       VALUES (?, ?, ?, 1, ?, ?)""",
                                    (
                                        tenant_id,
                                        normalized_slug,
                                        tenant_name.strip(),
                                        now(),
                                        developer["id"],
                                    ),
                                )
                                platform_audit(
                                    connection,
                                    developer["id"],
                                    "Tenant created",
                                    tenant_id,
                                    f"{tenant_name.strip()}; slug={normalized_slug}; "
                                    f"owner={first_owner_username.strip().lower()}",
                                )
                            st.success(
                                f"Tenant {tenant_name.strip()} and its first Owner / Super Admin "
                                "account were created."
                            )
                            st.rerun()
                        except (ValueError, RuntimeError, sqlite3.Error) as error:
                            if temp_path.exists():
                                temp_path.unlink()
                            if final_path_created and final_path.exists():
                                final_path.unlink()
                            st.error(str(error) or "The tenant could not be created.")
                        except Exception:
                            if temp_path.exists():
                                temp_path.unlink()
                            if final_path_created and final_path.exists():
                                final_path.unlink()
                            raise
    with audit_tab:
        with platform_database() as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """SELECT pa.created_at, pu.username AS developer, pa.action,
                              t.name AS tenant, pa.details
                       FROM platform_audit pa
                       LEFT JOIN platform_users pu ON pu.id = pa.platform_user_id
                       LEFT JOIN tenants t ON t.id = pa.tenant_id
                       ORDER BY pa.id DESC LIMIT 100"""
                ).fetchall()
            ]
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.info("No platform administration events have been recorded.")


def main():
    initialize_platform()
    st.markdown(
        """
        <style>
        .stApp,
        [data-testid="stAppViewContainer"] {
            background: #f4f8f9;
            color: #26331a;
            font-size: 16px;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stWidgetLabel"] {
            font-size: 16px;
            line-height: 1.5;
        }
        [data-testid="stCaptionContainer"] {
            font-size: 14px;
            line-height: 1.45;
        }
        [data-testid="stMarkdownContainer"] h1 { font-size: 2.125rem; line-height: 1.2; }
        [data-testid="stMarkdownContainer"] h2 { font-size: 1.75rem; line-height: 1.25; }
        [data-testid="stMarkdownContainer"] h3 { font-size: 1.4375rem; line-height: 1.3; }
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 { color: #005b60; }
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stDateInput"] input,
        [data-testid="stTimeInput"] input,
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stMultiSelect"] [role="combobox"] {
            font-size: 16px !important;
        }
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button {
            font-size: 16px;
        }
        [data-testid="stMetric"] { background: #fff; padding: 1rem; border: 1px solid #d5e4e6; border-radius: 12px; }
        div[data-testid="stForm"] { background: #fff; border: 1px solid #d5e4e6; border-radius: 12px; padding: 1rem; }
        section[data-testid="stSidebar"] { background: #005b60; }
        section[data-testid="stSidebar"] {
            color: #fff;
            font-size: 16px;
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        section[data-testid="stSidebar"] [data-testid="stRadio"] label,
        section[data-testid="stSidebar"] [data-testid="stButton"] button {
            font-size: 16px;
            line-height: 1.45;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button,
        section[data-testid="stSidebar"] [data-testid="stButton"] button p {
            color: #fff !important;
            background: #008b8b !important;
            border: 1px solid #008b8b !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            opacity: 1 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stButton"] button:hover,
        section[data-testid="stSidebar"] [data-testid="stButton"] button:hover p {
            color: #fff !important;
            background: #005b60 !important;
            border-color: #005b60 !important;
        }
        section[data-testid="stSidebar"] .st-key-sign_out button,
        section[data-testid="stSidebar"] .st-key-sign_out button p {
            color: #fff !important;
            background: #ff4b4b !important;
            border-color: #ff4b4b !important;
        }
        section[data-testid="stSidebar"] .st-key-sign_out button:hover,
        section[data-testid="stSidebar"] .st-key-sign_out button:hover p {
            color: #fff !important;
            background: #e03e3e !important;
            border-color: #e03e3e !important;
        }
        .st-key-login_screen [data-testid="stHorizontalBlock"] {
            min-height: calc(100vh - 8rem);
            align-items: center;
        }
        .st-key-login_screen [data-testid="stFormSubmitButton"] button {
            color: #fff !important;
            background: #ff4b4b !important;
            border: 1px solid #e03e3e !important;
        }
        .st-key-login_screen [data-testid="stFormSubmitButton"] button:hover {
            color: #fff !important;
            background: #e03e3e !important;
            border-color: #c92f2f !important;
        }
        @media (max-width: 700px) {
            .st-key-login_screen [data-testid="stHorizontalBlock"] {
                min-height: 0;
                align-items: flex-start;
            }
        }
        section[data-testid="stSidebar"] * { color: #fff; }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: #fff; }
        .stAlert { border-left-color: #e07a5f !important; }
        button[kind="primary"],
        button[data-testid="baseButton-primary"],
        [data-testid="stFormSubmitButton"] button {
            color: #fff !important;
            background: #008b8b !important;
            border: 1px solid #005b60 !important;
        }
        button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            color: #fff !important;
            background: #005b60 !important;
            border-color: #005b60 !important;
        }
        button[kind="secondary"],
        button[data-testid="baseButton-secondary"] {
            color: #005b60 !important;
            background: #fff !important;
            border: 1px solid #e07a5f !important;
        }
        button[kind="secondary"]:hover,
        button[data-testid="baseButton-secondary"]:hover {
            background: #fce9e4 !important;
            border-color: #e07a5f !important;
        }
        [data-testid="stTextInputRootElement"],
        [data-testid="stNumberInputRootElement"],
        [data-testid="stTextAreaRootElement"],
        [data-testid="stDateInputRootElement"],
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
            background-color: #fff !important;
            border: 2px solid #78a5a8 !important;
            border-radius: 8px !important;
        }
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stDateInput"] input,
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stMultiSelect"] [role="combobox"] {
            color: #26331a !important;
            background: transparent !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stTextInput"] input::placeholder,
        [data-testid="stTextArea"] textarea::placeholder {
            color: #607679 !important;
            opacity: 1;
        }
        [data-testid="stTextInputRootElement"]:focus-within,
        [data-testid="stNumberInputRootElement"]:focus-within,
        [data-testid="stTextAreaRootElement"]:focus-within,
        [data-testid="stDateInputRootElement"]:focus-within,
        [data-testid="stTimeInputRootElement"]:focus-within,
        [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within > div,
        [data-testid="stFileUploader"] section:focus-within,
        [data-testid="stDataEditor"]:focus-within {
            border-color: #008b8b !important;
            box-shadow: 0 0 0 2px rgb(0 139 139 / 20%) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stTextInput"] input,
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
        section[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"],
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [role="combobox"] {
            color: #26331a !important;
        }
        :root {
            --medscope-teal: #005b60;
            --medscope-bright: #008b8b;
            --medscope-coral: #e07a5f;
            --medscope-ink: #17383a;
            --medscope-muted: #607679;
            --medscope-border: #dce8e9;
            --medscope-canvas: #f4f8f9;
        }
        html, body, [class*="css"] {
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        }
        .stApp {
            background:
                radial-gradient(ellipse at 92% 0%, rgb(0 139 139 / 7%), transparent 32rem),
                var(--medscope-canvas);
            color: var(--medscope-ink);
        }
        header[data-testid="stHeader"] {
            background: rgb(244 248 249 / 88%);
            backdrop-filter: blur(12px);
        }
        .block-container {
            max-width: 1480px;
            padding-top: 2rem;
            padding-bottom: 3.5rem;
        }
        [data-testid="stMarkdownContainer"] h1 {
            color: var(--medscope-teal);
            font-size: clamp(1.8rem, 2.5vw, 2.35rem);
            font-weight: 720;
            letter-spacing: -0.035em;
            margin-bottom: .35rem;
        }
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            color: var(--medscope-teal);
            font-weight: 680;
            letter-spacing: -0.02em;
        }
        [data-testid="stCaptionContainer"] {
            color: var(--medscope-muted);
        }
        [data-testid="stMetric"] {
            min-height: 112px;
            padding: 1.15rem 1.25rem;
            border: 1px solid var(--medscope-border);
            border-top: 3px solid var(--medscope-bright);
            border-radius: 14px;
            background: linear-gradient(145deg, #fff, #fbfdfd);
            box-shadow: 0 5px 18px rgb(23 56 58 / 5%);
            transition: transform 160ms ease, box-shadow 160ms ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgb(23 56 58 / 9%);
        }
        [data-testid="stMetricLabel"] {
            color: var(--medscope-muted);
            font-size: .82rem;
            font-weight: 650;
            letter-spacing: .045em;
            text-transform: uppercase;
        }
        [data-testid="stMetricValue"] {
            color: var(--medscope-teal);
            font-weight: 730;
            letter-spacing: -.035em;
        }
        [data-testid="stMetricValue"] .currency-symbol {
            display: inline-block;
            font-size: .9em;
            font-weight: 760;
            vertical-align: baseline;
        }
        div[data-testid="stForm"] {
            border-color: var(--medscope-border);
            border-radius: 14px;
            padding: 1.25rem 1.35rem;
            box-shadow: 0 6px 22px rgb(23 56 58 / 5%);
        }
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid var(--medscope-border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 3px 14px rgb(23 56 58 / 4%);
        }
        [data-testid="stTabs"] [role="tablist"] {
            gap: .45rem;
            border-bottom: 1px solid var(--medscope-border);
        }
        [data-testid="stTabs"] button[role="tab"] {
            min-height: 42px;
            padding: .55rem 1rem;
            border-radius: 9px 9px 0 0;
            color: var(--medscope-muted);
            font-weight: 620;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: var(--medscope-teal);
            background: rgb(0 139 139 / 8%);
        }
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button {
            min-height: 42px;
            border-radius: 9px !important;
            font-weight: 650 !important;
            transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
        }
        [data-testid="stButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 12px rgb(0 91 96 / 16%);
        }
        [data-testid="stTextInputRootElement"],
        [data-testid="stNumberInputRootElement"],
        [data-testid="stTextAreaRootElement"],
        [data-testid="stDateInputRootElement"],
        [data-testid="stTimeInputRootElement"],
        [data-testid="stTextInput"] [data-baseweb="base-input"],
        [data-testid="stNumberInput"] [data-baseweb="input"],
        [data-testid="stTextArea"] [data-baseweb="textarea"],
        [data-testid="stDateInput"] [data-baseweb="input"],
        [data-testid="stTimeInput"] [data-baseweb="input"],
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        [data-testid="stFileUploader"] section,
        [data-testid="stDataEditor"] {
            border: 2px solid #78a5a8 !important;
            border-radius: 9px !important;
            box-shadow: 0 1px 2px rgb(23 56 58 / 3%);
        }
        [data-testid="stFileUploader"] section {
            border-style: dashed !important;
        }
        .stAlert {
            border-radius: 10px;
            box-shadow: 0 3px 12px rgb(23 56 58 / 4%);
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #005b60 0%, #064b50 100%);
            border-right: 1px solid rgb(255 255 255 / 10%);
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
            padding-bottom: .9rem;
            border-bottom: 1px solid rgb(255 255 255 / 18%);
            color: #fff;
            letter-spacing: -.035em;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
            gap: .28rem;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label {
            border: 1px solid transparent;
            border-radius: 9px;
            padding: .35rem .55rem;
            transition: background 140ms ease, border-color 140ms ease;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            background: rgb(255 255 255 / 9%);
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
            background: rgb(255 255 255 / 14%);
            border-color: rgb(255 255 255 / 22%);
        }
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: rgb(255 255 255 / 72%);
        }
        .st-key-login_screen [data-testid="stMarkdownContainer"] h1 {
            font-size: clamp(2.6rem, 4vw, 3.6rem);
            letter-spacing: -.055em;
        }
        .st-key-login_screen [data-testid="stCaptionContainer"] {
            font-size: 1rem;
        }
        .st-key-login_screen div[data-testid="stForm"] {
            padding: 1.4rem 1.5rem;
            border-color: rgb(0 91 96 / 10%);
            box-shadow: 0 18px 50px rgb(0 61 65 / 10%);
        }
        @media (max-width: 900px) {
            .block-container {
                padding: 1.25rem 1rem 2.5rem;
            }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                transition-duration: .01ms !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    theme_css_path = Path(__file__).with_name("theme.css")
    theme_css = theme_css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{theme_css}</style>", unsafe_allow_html=True)
    developer = st.session_state.get("platform_dev")
    dev_auto_login = os.getenv("MEDSCOPE_DEV_AUTO_LOGIN", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if dev_auto_login and not developer:
        initialize_platform()
        with platform_database() as connection:
            dev = connection.execute(
                """SELECT id, username, display_name
                   FROM platform_users
                   WHERE active = 1
                   ORDER BY id LIMIT 1"""
            ).fetchone()
        if dev:
            developer = {
                "id": dev["id"],
                "username": dev["username"],
                "name": dev["display_name"],
            }
            st.session_state["platform_dev"] = developer
            st.session_state["platform_dev_authenticated_at"] = time.time()
    elif dev_auto_login and developer:
        st.session_state["platform_dev_authenticated_at"] = time.time()
    if developer:
        authenticated_at = st.session_state.get("platform_dev_authenticated_at", 0)
        with platform_database() as connection:
            current_dev = connection.execute(
                "SELECT active FROM platform_users WHERE id = ?",
                (developer["id"],),
            ).fetchone()
        if (
            current_dev is None
            or not current_dev["active"]
            or time.time() - authenticated_at > 3600
        ):
            st.session_state.pop("platform_dev", None)
            st.session_state.pop("platform_dev_authenticated_at", None)
            st.session_state.pop("tenant_dev_actor", None)
            st.session_state.pop("staff", None)
            st.session_state.pop("tenant_id", None)
            st.session_state.pop("tenant_db_path", None)
            developer = None
            st.warning("The Dev session expired or was disabled. Sign in again.")

    staff = st.session_state.get("staff")
    tenant_id = st.session_state.get("tenant_id")
    tenant_dev_actor = st.session_state.get("tenant_dev_actor")
    if developer and not tenant_dev_actor:
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"],
            [data-testid="collapsedControl"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    if developer and not tenant_dev_actor:
        dev_portal(developer)
        return
    if staff and tenant_id:
        with platform_database() as connection:
            tenant = connection.execute(
                "SELECT id, name, active FROM tenants WHERE id = ?",
                (tenant_id,),
            ).fetchone()
        if tenant is None:
            st.session_state.pop("staff", None)
            st.session_state.pop("tenant_id", None)
            st.session_state.pop("tenant_db_path", None)
            st.error("This tenant is no longer available.")
            login_screen()
            return
        if not tenant["active"] and not tenant_dev_actor:
            st.session_state.pop("staff", None)
            st.session_state.pop("tenant_id", None)
            st.session_state.pop("tenant_db_path", None)
            st.error("This diagnostic center has been disabled. Contact MedScope Dev.")
            login_screen()
            return
        tenant_path = tenant_database_path(tenant_id)
        if not tenant_path.is_file():
            st.error(
                "The tenant database file is missing. Sign-in is blocked to protect tenant data; "
                "restore it from backup before continuing."
            )
            st.stop()
        st.session_state["tenant_db_path"] = str(tenant_path)
        initialize_database(tenant_path)
        if tenant_dev_actor:
            st.info(
                f"Platform Dev administration · {tenant['name']} · "
                "Actions are audited under your Dev identity."
            )
    else:
        st.session_state.pop("staff", None)
        st.session_state.pop("tenant_dev_actor", None)
        login_screen()
        return
    if staff["role"] not in ROLES:
        st.error("This role does not have access to the receptionist module.")
        return

    with st.sidebar:
        st.markdown(f"## ✚ {APP_NAME}")
        st.caption(tenant["name"] if tenant else "Diagnostic center")
        st.write(f"Signed in: **{staff['name']}**")
        st.caption(staff["role"])
        if tenant_dev_actor:
            st.caption(f"Platform Dev: {tenant_dev_actor}")
        standard_pages = (
            "Dashboard",
            "Find Patient",
            "New Invoice",
            "Invoices",
            "Dues",
            "Test Assignment",
            "Report Delivery",
            "Inventory",
            "Accounts & Referrers",
            "Database Management",
            "Day Open / Close",
        )
        if staff["role"] == "Lab Tech":
            available_pages = ("Dashboard", "Lab Work")
        elif staff["role"] == "Owner":
            available_pages = (
                *standard_pages[:5],
                "Lab Work",
                *standard_pages[5:],
                "Reports",
                "Audit Trail",
                "Accounting",
            )
        elif staff["role"] == "Admin":
            available_pages = (*standard_pages[:5], "Lab Work", *standard_pages[5:], "Audit Trail")
        else:
            available_pages = tuple(
                available_page
                for available_page in standard_pages
                if available_page not in ("Accounts & Referrers", "Database Management")
            )
        if st.session_state.get("navigation_page") not in available_pages:
            st.session_state["navigation_page"] = "Dashboard"
        page = st.radio(
            "Navigate",
            available_pages,
            key="navigation_page",
        )
        if tenant_dev_actor and st.button(
            "Return to Dev module",
            use_container_width=True,
            key="return_to_dev",
        ):
            st.session_state.pop("staff", None)
            st.session_state.pop("tenant_dev_actor", None)
            st.session_state.pop("tenant_id", None)
            st.session_state.pop("tenant_db_path", None)
            st.session_state.pop("navigation_page", None)
            st.rerun()
        if st.button("Sign out", use_container_width=True, key="sign_out"):
            st.session_state.pop("staff", None)
            st.session_state.pop("tenant_dev_actor", None)
            st.session_state.pop("tenant_id", None)
            st.session_state.pop("tenant_db_path", None)
            st.session_state.pop("platform_dev", None)
            st.session_state.pop("platform_dev_authenticated_at", None)
            st.rerun()
        st.caption("Separate SQLite database per tenant · Single app instance")

    if page != "Dashboard":
        st.button(
            "← Back to dashboard",
            key="back_to_dashboard",
            on_click=go_to_page,
            args=("Dashboard",),
        )

    if page == "Dashboard":
        dashboard(staff)
    elif page == "Find Patient":
        patient_search()
    elif page == "New Invoice":
        new_invoice(staff)
    elif page == "Invoices":
        invoice_search(staff)
    elif page == "Dues":
        dues_screen(staff)
    elif page == "Test Assignment":
        assignment_screen(staff)
    elif page == "Lab Work":
        lab_work_screen(staff)
    elif page == "Report Delivery":
        report_delivery_screen(staff)
    elif page == "Inventory":
        inventory_screen(staff)
    elif page == "Accounts & Referrers":
        account_management(staff)
    elif page == "Database Management":
        database_management(staff)
    elif page == "Day Open / Close":
        day_management(staff)
    elif page == "Reports":
        user_reports_screen(staff)
    elif page == "Audit Trail":
        audit_screen(staff)
    elif page == "Accounting":
        accounting_screen(staff)


main()

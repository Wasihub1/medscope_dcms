"""
Prompt 19B (Module 23): the handful of tests for properties that cannot be checked any other way.
- the database refuses UPDATE / DELETE / TRUNCATE on audit_logs (no bypass in the trigger itself)
- no code under backend/ deletes or purges audit rows (retention: kept forever)
- discount / initial-payment / report-view events are written with real before/after
- reprints are written to audit_logs (reprint_logs is gone) and the print counter still counts
- the viewer filters (domain, acting role, free text) and the CSV export respects them and audits itself
Runs only against medscope_test (conftest guard).
"""
import csv
import io
import re
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from backend.app.core.audit_domains import domain_labels, domain_of
from backend.app.models.audit import AuditLog
from backend.app.models.patient import Patient
from backend.app.models.test import Test
from tests.conftest import ADMIN_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS
from tests.test_prompt16_final_reports import _fin, _tech_order

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def _body(db, discount=None, master=None, paid=0, extra_lines=None):
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    hgb = db.execute(select(Test.id).where(Test.code == "HGB")).scalar_one()
    rbs = db.execute(select(Test.id).where(Test.code == "RBS")).scalar_one()
    line = {"test_id": hgb}
    if discount:
        line.update(discount_type=discount[0], discount_value=discount[1])
    body = {"patient_id": pid, "age_value": 35, "gender": "Male", "lines": [line, {"test_id": rbs}],
            "initial_payment_amount": paid, "initial_payment_method": "CASH"}
    if master:
        body.update(bill_discount_type=master[0], bill_discount_value=master[1])
    return body


def _rows(db, action, entity_id=None):
    db.expire_all()
    q = select(AuditLog).where(AuditLog.action == action)
    if entity_id is not None:
        q = q.where(AuditLog.entity_id == str(entity_id))
    return db.execute(q.order_by(AuditLog.id)).scalars().all()


# ------------------------------------------------------------------ immutability
def test_database_refuses_update_delete_and_truncate_on_audit_logs(db_session):
    row = db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().first()
    assert row is not None
    for sql in ("UPDATE audit_logs SET action = 'TAMPERED' WHERE id = :i", "DELETE FROM audit_logs WHERE id = :i"):
        with pytest.raises(DBAPIError, match="append-only"):
            db_session.execute(text(sql), {"i": row.id})
        db_session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(text("TRUNCATE audit_logs"))
    db_session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):  # the ORM path too
        db_session.delete(db_session.get(AuditLog, row.id))
        db_session.flush()
    db_session.rollback()
    assert db_session.get(AuditLog, row.id).action == row.action


def test_reprint_logs_table_is_gone_and_no_code_still_mentions_it():
    from backend.app.core.database import engine
    with engine.connect() as c:
        assert c.execute(text("SELECT to_regclass('public.reprint_logs')")).scalar() is None
    for f in BACKEND.rglob("*.py"):
        if "alembic" in f.parts or "__pycache__" in f.parts:
            continue
        src = f.read_text(encoding="utf-8")
        assert "ReprintLog" not in src and '"reprint_logs"' not in src and not re.search(r"(from|into|update)\s+reprint_logs", src, re.I), f


def test_no_application_code_deletes_or_purges_audit_rows():
    """Retention: kept forever. Nothing under backend/ (outside migrations) may delete, truncate or purge audit_logs."""
    pattern = re.compile(r"delete\s+from\s+audit_logs|truncate\s+(table\s+)?audit_logs|drop\s+table\s+audit_logs|update\s+audit_logs"
                         r"|delete\(\s*AuditLog|\.delete\(.*audit|purge_audit|AuditLog\)\s*\.delete", re.I)
    offenders = []
    for f in BACKEND.rglob("*"):
        if f.suffix not in (".py", ".sql", ".ps1") or "alembic" in f.parts or "__pycache__" in f.parts:
            continue
        if pattern.search(f.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(f.relative_to(BACKEND)))
    assert offenders == []
    # and no route can delete or modify the audit log
    from backend.app.main import app
    for r in app.routes:
        if "/audit-logs" in getattr(r, "path", ""):
            assert (getattr(r, "methods", None) or set()) <= {"GET", "HEAD"}, r.path


# ------------------------------------------------------------------ discounts
def test_draft_discount_edit_writes_before_and_after_and_confirm_records_final_state(client, db_session):
    d = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=_body(db_session))
    assert d.status_code == 201
    iid = d.json()["id"]
    assert _rows(db_session, "INVOICE_DISCOUNT_CHANGED", iid) == []  # no discount, nothing to record

    e1 = client.put(f"/invoices/{iid}/draft", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("PERCENTAGE", 10)))
    assert e1.status_code == 200
    e2 = client.put(f"/invoices/{iid}/draft", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("AMOUNT", 40)))
    assert e2.status_code == 200
    e3 = client.put(f"/invoices/{iid}/draft", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("AMOUNT", 40), master=("PERCENTAGE", 5)))
    assert e3.status_code == 200
    client.put(f"/invoices/{iid}/draft", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("AMOUNT", 40), master=("PERCENTAGE", 5)))  # unchanged: no new row
    rows = _rows(db_session, "INVOICE_DISCOUNT_CHANGED", iid)
    assert len(rows) == 3
    assert rows[0].before_value == "No discount" and "PERCENTAGE 10" in rows[0].after_value and "PERCENTAGE 10" in rows[0].after_value
    assert "PERCENTAGE 10" in rows[1].before_value and "AMOUNT 40" in rows[1].after_value
    assert "AMOUNT 40" in rows[2].before_value and "Master PERCENTAGE 5" in rows[2].after_value and "inactive while the master" in rows[2].after_value
    assert all(r.acting_role == "RECEPTIONIST" and r.actor_id for r in rows)

    assert client.post(f"/invoices/{iid}/finalize", headers=RECEPTIONIST_HEADERS).status_code == 200
    conf = _rows(db_session, "INVOICE_DISCOUNT_CONFIRMED", iid)
    assert len(conf) == 1 and "Master PERCENTAGE 5" in conf[0].before_value and "Master PERCENTAGE 5" in conf[0].after_value
    assert "Total discount Tk" in conf[0].after_value


def test_direct_confirm_with_a_discount_records_before_none_and_no_discount_records_nothing(client, db_session):
    plain = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_body(db_session))
    assert plain.status_code == 201 and _rows(db_session, "INVOICE_DISCOUNT_CONFIRMED", plain.json()["id"]) == []
    disc = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("PERCENTAGE", 20)))
    assert disc.status_code == 201
    row = _rows(db_session, "INVOICE_DISCOUNT_CONFIRMED", disc.json()["id"])
    assert len(row) == 1 and row[0].before_value == "No discount" and "PERCENTAGE 20" in row[0].after_value


# ------------------------------------------------------------------ initial payment
def test_initial_payment_has_its_own_event_separate_from_confirm(client, db_session):
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_body(db_session, paid=100))
    assert res.status_code == 201
    iid = res.json()["id"]
    pay_id = res.json()["payments"][0]["id"]
    ev = _rows(db_session, "INVOICE_INITIAL_PAYMENT", pay_id)
    assert len(ev) == 1 and ev[0].entity_type == "PAYMENT"
    assert "Tk 100 via CASH" in ev[0].after_value and "payer:" in ev[0].after_value and "received by:" in ev[0].after_value
    assert "paid Tk 0" in ev[0].before_value
    assert len(_rows(db_session, "CONFIRM_INVOICE", iid)) == 1  # the confirm row is still there
    nopay = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_body(db_session))
    assert db_session.execute(select(AuditLog).where(AuditLog.action == "INVOICE_INITIAL_PAYMENT", AuditLog.after_value.contains(nopay.json()["invoice_no"]))).first() is None


# ------------------------------------------------------------------ report views and reprints
def test_every_report_open_writes_one_row_with_no_throttling_and_a_404_writes_none(client, db_session):
    rid = _fin(client, _tech_order(client, db_session)).json()["report_version_id"]
    for _ in range(2):
        assert client.get(f"/reports/{rid}/snapshot", headers=RECEPTIONIST_HEADERS).status_code == 200
    assert client.get(f"/reports/{rid}", headers=RECEPTIONIST_HEADERS).status_code == 200
    rows = _rows(db_session, "REPORT_VIEWED", rid)
    assert len(rows) == 3 and all(r.entity_type == "REPORT" and r.acting_role == "RECEPTIONIST" and r.actor_id for r in rows)
    assert "snapshot" in rows[0].after_value and "report detail" in rows[2].after_value
    before = len(_rows(db_session, "REPORT_VIEWED"))
    assert client.get("/reports/99999999/snapshot", headers=RECEPTIONIST_HEADERS).status_code == 404
    assert len(_rows(db_session, "REPORT_VIEWED")) == before


def test_ready_result_preview_is_logged_with_the_order_id(client, db_session):
    oid = _tech_order(client, db_session)
    assert client.get(f"/reports/ready/{oid}/preview", headers=RECEPTIONIST_HEADERS).status_code == 200
    rows = _rows(db_session, "REPORT_PREVIEW_VIEWED", oid)
    assert len(rows) == 1 and rows[0].entity_type == "REPORT" and "test order" in rows[0].after_value


def test_reprints_go_to_audit_logs_and_the_print_counter_still_counts(client, db_session):
    rid = _fin(client, _tech_order(client, db_session)).json()["report_version_id"]
    client.put("/settings", headers=OWNER_HEADERS, json={"report_hold_when_due": False})
    try:
        first = client.get(f"/reports/printable/{rid}", headers=RECEPTIONIST_HEADERS).json()
        second = client.get(f"/reports/printable/{rid}", headers=RECEPTIONIST_HEADERS).json()
    finally:
        client.put("/settings", headers=OWNER_HEADERS, json={"report_hold_when_due": True})
    assert first["reprint_count"] == 1 and second["reprint_count"] == 2 and second["is_duplicate"] is True
    rows = _rows(db_session, "REPORT_REPRINTED", rid)
    assert len(rows) == 2 and rows[1].before_value == "1 earlier print(s)" and rows[1].acting_role == "RECEPTIONIST"
    assert rows[1].after_value.startswith("Print #2")


# ------------------------------------------------------------------ viewer: domains, role, search, export
def test_domain_grouping_covers_every_known_action_and_unknown_ones_fall_into_other():
    assert domain_of("INVOICE_DISCOUNT_CHANGED") == "discounts" and domain_of("REPORT_VIEWED") == "reports"
    assert domain_of("REFUND_DISBURSED") == "payments" and domain_of("CLOSE_BUSINESS_DAY") == "accounting"
    assert domain_of("SETTING_CHANGED") == "settings" and domain_of("USER_PERMISSIONS_CHANGED") == "permissions"
    assert domain_of("STOCK_CONSUMPTION_INTEGRATION_TRIGGERED") == "stock" and domain_of("CONFIRM_INVOICE") == "bills"
    assert domain_of("TEST_DATA_CLEANUP") == "other" and domain_of("SOMETHING_NEW") == "other"
    assert {d["key"] for d in domain_labels()} >= {"bills", "discounts", "payments", "reports", "stock", "accounting", "settings", "permissions"}


def test_viewer_filters_by_domain_role_and_free_text_and_stays_read_only(client, db_session):
    client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("PERCENTAGE", 15)))
    meta = client.get("/audit-logs/meta", headers=OWNER_HEADERS).json()
    assert {"discounts", "other"} <= {d["key"] for d in meta["domains"]} and "RECEPTIONIST" in meta["roles"] and meta["actors"]

    r = client.get("/audit-logs", headers=OWNER_HEADERS, params={"domain": "discounts", "size": 200}).json()
    assert r["total"] >= 1 and all(i["domain"] == "discounts" for i in r["items"])
    r = client.get("/audit-logs", headers=OWNER_HEADERS, params={"acting_role": "RECEPTIONIST", "size": 200}).json()
    assert r["total"] >= 1 and all(i["acting_role"] == "RECEPTIONIST" for i in r["items"])
    r = client.get("/audit-logs", headers=OWNER_HEADERS, params={"q": "PERCENTAGE 15", "size": 200}).json()
    assert r["total"] >= 1 and all("PERCENTAGE 15" in ((i["before_value"] or "") + (i["after_value"] or "")) for i in r["items"])
    assert client.get("/audit-logs", headers=OWNER_HEADERS, params={"q": "no-such-text-" + "x" * 12}).json()["total"] == 0
    # a "%" typed in the box is literal text, not a wildcard
    assert client.get("/audit-logs", headers=OWNER_HEADERS, params={"q": "%zz%"}).json()["total"] == 0
    # permission and read-only
    assert client.get("/audit-logs", headers=RECEPTIONIST_HEADERS).status_code == 403
    assert client.get("/audit-logs/export", headers=ADMIN_HEADERS).status_code == 403
    for m in (client.put, client.patch, client.delete):
        assert m("/audit-logs", headers=OWNER_HEADERS).status_code in (404, 405)


def test_export_is_csv_with_bom_respects_filters_and_audits_itself(client, db_session):
    client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_body(db_session, discount=("PERCENTAGE", 25)))
    params = {"domain": "discounts", "acting_role": "RECEPTIONIST", "q": "PERCENTAGE 25"}
    listed = client.get("/audit-logs", headers=OWNER_HEADERS, params={**params, "size": 200}).json()
    res = client.get("/audit-logs/export", headers=OWNER_HEADERS, params=params)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert 'filename="audit-log.csv"' in res.headers["content-disposition"]
    body = res.content.decode("utf-8")
    assert body.startswith("﻿")
    rows = list(csv.DictReader(io.StringIO(body.lstrip("﻿"))))
    assert len(rows) == listed["total"] >= 1
    assert all(r["domain"] == "discounts" and r["acting_role"] == "RECEPTIONIST" for r in rows)
    assert list(rows[0].keys()) == ["id", "when_utc", "actor", "actor_id", "acting_role", "domain", "action", "entity_type", "entity_id", "reason", "before", "after"]
    # the export wrote its own audit row: who, filters, row count
    own = _rows(db_session, "AUDIT_LOG_EXPORTED")[-1]
    assert own.acting_role == "OWNER" and own.actor_id and f"Exported {len(rows)} row(s)" in own.after_value
    assert "discounts" in own.after_value and "RECEPTIONIST" in own.after_value and "PERCENTAGE 25" in own.after_value
    assert domain_of("AUDIT_LOG_EXPORTED") == "audit"


def test_export_neutralises_spreadsheet_formulas(client, db_session):
    from backend.app.services.audit_service import log_audit_event
    log_audit_event(db_session, "center-seba-01", "FORMULA_PROBE", "PROBE", "1", "OWNER", None, before_value="=1+1", after_value="@SUM(A1)")
    db_session.commit()
    res = client.get("/audit-logs/export", headers=OWNER_HEADERS, params={"action": "FORMULA_PROBE"})
    rows = list(csv.DictReader(io.StringIO(res.content.decode("utf-8").lstrip("﻿"))))
    assert rows and all(r["before"] == "'=1+1" and r["after"] == "'@SUM(A1)" for r in rows)

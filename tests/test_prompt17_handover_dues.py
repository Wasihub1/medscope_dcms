"""
Prompt 17 - Module 17 (report handover) and Module 18 (dues): center settings, held-report setting,
handover search / has_due filter / log / reprint, dues aging and call list, write-off (D11) and the
two doctor balances (D43). Runs only against medscope_test (conftest guard).
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.core.permissions import ROLE_DEFAULTS
from backend.app.core.timezone import utc_now
from backend.app.models.audit import AuditLog
from backend.app.models.dues import DoctorBalanceEntry, DueWriteOff
from backend.app.models.invoice import Invoice
from backend.app.models.report import ReportDelivery
from backend.app.models.test_order import TestOrder
from tests.conftest import ADMIN_HEADERS, CASHIER_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS
from tests.test_prompt15_doctor_signoff import _doctor
from tests.test_prompt16_final_reports import _fin, _tech_order


@pytest.fixture(autouse=True)
def _restore_settings(client):
    yield
    client.put("/settings", headers=OWNER_HEADERS, json={"report_hold_when_due": True, "writeoff_admin_limit": 500, "cash_variance_tolerance": 0})


def _due_invoice(client, db):
    """A confirmed invoice (net 300, nothing paid) with a submitted and finalized report. Returns (order_id, invoice_id, report_id)."""
    oid = _tech_order(client, db)
    rid = _fin(client, oid).json()["report_version_id"]
    db.expire_all()
    return oid, db.get(TestOrder, oid).invoice_line.invoice_id, rid


def _inv(db, iid):
    db.expire_all()
    return db.get(Invoice, iid)


def _deliver(client, rid, headers, reason=None):
    body = {"delivered_to_name": "Relative", "delivered_to_relation": "Spouse"}
    if reason:
        body["admin_due_override_reason"] = reason
    return client.post(f"/reports/deliver/{rid}", headers=headers, json=body)


# ---------------------------------------------------------------- permissions and settings
def test_permission_keys_and_role_matrix():
    assert "settings.manage" in ROLE_DEFAULTS["OWNER"] and "settings.manage" not in ROLE_DEFAULTS["ADMIN"]
    for key in ("due.writeoff", "doctor_balance.view"):
        assert key in ROLE_DEFAULTS["OWNER"] and key in ROLE_DEFAULTS["ADMIN"]
        assert not any(key in ROLE_DEFAULTS[r] for r in ("RECEPTIONIST", "CASHIER", "LAB_TECH", "DOCTOR"))


def test_settings_read_defaults_and_owner_only_edit(client, db_session):
    assert client.get("/settings", headers=RECEPTIONIST_HEADERS).json() == {"report_hold_when_due": True, "writeoff_admin_limit": 500, "cash_variance_tolerance": 0}
    assert client.put("/settings", headers=ADMIN_HEADERS, json={"writeoff_admin_limit": 5}).status_code == 403
    assert client.put("/settings", headers=RECEPTIONIST_HEADERS, json={"report_hold_when_due": False}).status_code == 403
    r = client.put("/settings", headers=OWNER_HEADERS, json={"writeoff_admin_limit": 800, "report_hold_when_due": False})
    assert r.status_code == 200 and r.json() == {"report_hold_when_due": False, "writeoff_admin_limit": 800, "cash_variance_tolerance": 0}
    assert client.get("/settings", headers=ADMIN_HEADERS).json()["writeoff_admin_limit"] == 800
    assert client.put("/settings", headers=OWNER_HEADERS, json={"writeoff_admin_limit": -1}).status_code == 422
    rows = db_session.execute(select(AuditLog).where(AuditLog.action == "SETTING_CHANGED", AuditLog.entity_id == "writeoff_admin_limit")).scalars().all()
    assert any(a.before_value == "500" and a.after_value == "800" and a.acting_role == "OWNER" for a in rows)


# ---------------------------------------------------------------- held-report setting and handover
def test_report_is_held_while_due_by_default_and_released_by_admin_with_reason(client, db_session):
    oid, iid, rid = _due_invoice(client, db_session)
    item = next(i for i in client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"limit": 100}).json() if i["report_version_id"] == rid)
    assert item["is_held_due_to_balance"] is True and item["invoice_due"] == 300 and item["can_deliver"] is False
    assert _deliver(client, rid, RECEPTIONIST_HEADERS, "pls").status_code == 403
    assert _deliver(client, rid, ADMIN_HEADERS).status_code == 400  # reason required
    ok = _deliver(client, rid, ADMIN_HEADERS, "Patient promised to pay tomorrow")
    assert ok.status_code == 201
    d = db_session.execute(select(ReportDelivery).where(ReportDelivery.report_version_id == rid)).scalar_one()
    assert d.delivered_with_due is True and d.due_release_reason and d.delivered_by_id and d.delivered_at
    log = db_session.execute(select(AuditLog).where(AuditLog.action == "DELIVER_REPORT", AuditLog.entity_id == str(rid))).scalar_one()
    assert "released despite due" in log.after_value and log.acting_role == "ADMIN"


def test_paying_the_due_inline_releases_the_hold_without_override(client, db_session):
    oid, iid, rid = _due_invoice(client, db_session)
    assert _deliver(client, rid, RECEPTIONIST_HEADERS).status_code == 403
    pay = client.post(f"/invoices/{iid}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 300, "method": "CASH"})
    assert pay.status_code == 201, pay.text
    assert _inv(db_session, iid).due == 0
    assert _deliver(client, rid, RECEPTIONIST_HEADERS).status_code == 201
    d = db_session.execute(select(ReportDelivery).where(ReportDelivery.report_version_id == rid)).scalar_one()
    assert d.delivered_with_due is False and d.due_release_reason is None


def test_setting_off_means_reports_are_never_held(client, db_session):
    oid, iid, rid = _due_invoice(client, db_session)
    assert client.put("/settings", headers=OWNER_HEADERS, json={"report_hold_when_due": False}).status_code == 200
    item = next(i for i in client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"limit": 100}).json() if i["report_version_id"] == rid)
    assert item["is_held_due_to_balance"] is False and item["can_deliver"] is True and item["invoice_due"] == 300
    assert _deliver(client, rid, RECEPTIONIST_HEADERS).status_code == 201  # no reason, no Admin needed
    log = db_session.execute(select(AuditLog).where(AuditLog.action == "DELIVER_REPORT", AuditLog.entity_id == str(rid))).scalar_one()
    assert "hold setting off" in log.after_value
    # turning it back on holds the next one again
    client.put("/settings", headers=OWNER_HEADERS, json={"report_hold_when_due": True})
    oid2, iid2, rid2 = _due_invoice(client, db_session)
    assert _deliver(client, rid2, RECEPTIONIST_HEADERS).status_code == 403


def test_handover_search_finds_by_bill_patient_no_test_mobile_name_and_temp_bill(client, db_session):
    oid, iid, rid = _due_invoice(client, db_session)
    inv = _inv(db_session, iid)
    inv.temp_invoice_id = f"TMP-{uuid4().hex[:6].upper()}"
    db_session.commit()
    order = db_session.get(TestOrder, oid)
    pat = inv.patient
    terms = {
        "bill no": inv.invoice_no, "temporary bill": inv.temp_invoice_id, "patient no": pat.patient_code,
        "test name": order.invoice_line.test_name_snapshot, "mobile": pat.phone, "name": pat.name,
    }
    for label, term in terms.items():
        found = {i["report_version_id"] for i in client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"q": term, "limit": 100}).json()}
        assert rid in found, label
    assert rid not in {i["report_version_id"] for i in client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"q": "no-such-thing-xyz"}).json()}
    # has_due filter
    with_due = {i["report_version_id"] for i in client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"has_due": True, "limit": 100}).json()}
    without = {i["report_version_id"] for i in client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"has_due": False, "limit": 100}).json()}
    assert rid in with_due and rid not in without


def test_reprint_reuses_the_existing_duplicate_log(client, db_session):
    oid, iid, rid = _due_invoice(client, db_session)
    client.put("/settings", headers=OWNER_HEADERS, json={"report_hold_when_due": False})
    assert _deliver(client, rid, RECEPTIONIST_HEADERS).status_code == 201
    before = db_session.execute(select(AuditLog).where(AuditLog.action == "REPORT_REPRINTED", AuditLog.entity_type == "REPORT", AuditLog.entity_id == str(rid)).order_by(AuditLog.id)).scalars().all()
    r = client.get(f"/reports/printable/{rid}", headers=RECEPTIONIST_HEADERS)
    assert r.status_code == 200 and r.json()["is_duplicate"] is True
    db_session.expire_all()
    after = db_session.execute(select(AuditLog).where(AuditLog.action == "REPORT_REPRINTED", AuditLog.entity_type == "REPORT", AuditLog.entity_id == str(rid)).order_by(AuditLog.id)).scalars().all()
    assert len(after) == len(before) + 1 and after[-1].actor_id and after[-1].acting_role


# ---------------------------------------------------------------- dues aging and call list
def test_dues_list_carries_age_bucket_and_filters(client, db_session):
    _, iid, _ = _due_invoice(client, db_session)
    inv = _inv(db_session, iid)
    inv.created_at = utc_now() - timedelta(days=40)
    db_session.commit()
    items = client.get("/dues", headers=RECEPTIONIST_HEADERS, params={"limit": 100, "bucket": "31-90"}).json()
    row = next(i for i in items if i["invoice_id"] == iid)
    assert row["age_bucket"] == "31-90" and row["age_days"] >= 40 and row["due"] == 300 and row["written_off"] == 0
    assert iid not in {i["invoice_id"] for i in client.get("/dues", headers=RECEPTIONIST_HEADERS, params={"limit": 100, "bucket": "0-7"}).json()}
    # search by patient number now works (it was exact-match on name and phone only before)
    code = inv.patient.patient_code
    assert iid in {i["invoice_id"] for i in client.get("/dues", headers=RECEPTIONIST_HEADERS, params={"q": code, "bucket": "31-90", "limit": 100}).json()}


@pytest.mark.parametrize("days,bucket", [(0, "0-7"), (7, "0-7"), (8, "8-30"), (30, "8-30"), (31, "31-90"), (90, "31-90"), (91, "90+")])
def test_age_bucket_boundaries(days, bucket):
    from backend.app.services.dues_service import age_bucket
    assert age_bucket(days) == bucket


def test_call_list_groups_by_patient_oldest_first_and_is_derived(client, db_session):
    _, i1, _ = _due_invoice(client, db_session)
    _, i2, _ = _due_invoice(client, db_session)
    a, b = _inv(db_session, i1), _inv(db_session, i2)
    b.patient_id = a.patient_id  # same patient, two bills
    a.created_at = utc_now() - timedelta(days=95)
    b.created_at = utc_now() - timedelta(days=3)
    db_session.commit()
    body = client.get("/dues/call-list", headers=RECEPTIONIST_HEADERS).json()
    row = next(p for p in body["patients"] if p["patient_id"] == a.patient_id)
    assert row["invoice_count"] >= 2 and row["oldest_age_days"] >= 95 and row["age_bucket"] == "90+"
    ages = {x["invoice_id"]: x["age_bucket"] for x in row["invoices"]}
    assert ages[i1] == "90+" and ages[i2] == "0-7"
    assert row["total_due"] == sum(x["due"] for x in row["invoices"])
    assert sum(body["bucket_totals"].values()) == body["total_due"]
    order = [p["oldest_age_days"] for p in body["patients"]]
    assert order == sorted(order, reverse=True)
    # paying removes the bill from the list (nothing stored: derived)
    assert client.post(f"/invoices/{i1}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 300, "method": "CASH"}).status_code == 201
    row2 = next(p for p in client.get("/dues/call-list", headers=RECEPTIONIST_HEADERS).json()["patients"] if p["patient_id"] == a.patient_id)
    assert i1 not in {x["invoice_id"] for x in row2["invoices"]}
    assert client.get("/dues/call-list", headers=RECEPTIONIST_HEADERS, params={"bucket": "bad"}).status_code == 400
    assert client.get("/dues/call-list", headers=TECH_KAMAL_HEADERS).status_code == 403


# ---------------------------------------------------------------- write-off (D11)
def test_admin_writes_off_within_limit_directly_and_discount_is_untouched(client, db_session):
    _, iid, _ = _due_invoice(client, db_session)
    before = _inv(db_session, iid)
    snapshot = (before.gross, before.discount, before.net, before.paid)
    r = client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 200, "reason": "Patient cannot pay"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "APPLIED"
    inv = _inv(db_session, iid)
    assert inv.due == 100 and inv.written_off == 200
    assert (inv.gross, inv.discount, inv.net, inv.paid) == snapshot  # never mixed with discount
    w = db_session.execute(select(DueWriteOff).where(DueWriteOff.invoice_id == iid)).scalar_one()
    assert w.status == "APPLIED" and w.requested_by_role == "ADMIN" and w.reason == "Patient cannot pay"
    log = db_session.execute(select(AuditLog).where(AuditLog.action == "DUE_WRITTEN_OFF", AuditLog.entity_id == str(iid))).scalar_one()
    assert "Not a discount" in log.after_value
    # no payment row and no drawer effect: the remaining due can still be collected
    assert client.post(f"/invoices/{iid}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 100, "method": "CASH"}).status_code == 201
    inv = _inv(db_session, iid)
    assert inv.due == 0 and inv.paid == 100 and inv.written_off == 200


def test_admin_above_limit_needs_owner_approval(client, db_session):
    client.put("/settings", headers=OWNER_HEADERS, json={"writeoff_admin_limit": 100})
    _, iid, _ = _due_invoice(client, db_session)
    r = client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 150, "reason": "Hardship"})
    assert r.status_code == 201 and r.json()["status"] == "PENDING_OWNER"
    assert _inv(db_session, iid).due == 300 and _inv(db_session, iid).written_off == 0  # nothing changed yet
    wid = r.json()["id"]
    # one pending request per invoice; Admin cannot approve; Receptionist cannot see or act
    assert client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 10, "reason": "x"}).status_code == 409
    assert client.post(f"/dues/write-offs/{wid}/approve", headers=ADMIN_HEADERS).status_code == 403
    assert client.get("/dues/write-offs", headers=RECEPTIONIST_HEADERS).status_code == 403
    pend = client.get("/dues/write-offs", headers=OWNER_HEADERS, params={"status": "PENDING_OWNER"}).json()
    assert wid in {p["id"] for p in pend}
    ok = client.post(f"/dues/write-offs/{wid}/approve", headers=OWNER_HEADERS, json={"note": "ok"})
    assert ok.status_code == 200 and ok.json()["status"] == "APPLIED" and ok.json()["decided_by_name"]
    inv = _inv(db_session, iid)
    assert inv.due == 150 and inv.written_off == 150
    assert client.post(f"/dues/write-offs/{wid}/approve", headers=OWNER_HEADERS).status_code == 409  # already decided


def test_owner_reject_changes_nothing_and_owner_can_write_off_any_amount(client, db_session):
    client.put("/settings", headers=OWNER_HEADERS, json={"writeoff_admin_limit": 50})
    _, i1, _ = _due_invoice(client, db_session)
    wid = client.post(f"/invoices/{i1}/write-off", headers=ADMIN_HEADERS, json={"amount": 100, "reason": "r"}).json()["id"]
    rej = client.post(f"/dues/write-offs/{wid}/reject", headers=OWNER_HEADERS, json={"note": "no"})
    assert rej.status_code == 200 and rej.json()["status"] == "REJECTED"
    assert _inv(db_session, i1).due == 300 and _inv(db_session, i1).written_off == 0
    # the Owner has no limit and no second step
    big = client.post(f"/invoices/{i1}/write-off", headers=OWNER_HEADERS, json={"amount": 300, "reason": "Closed"})
    assert big.status_code == 201 and big.json()["status"] == "APPLIED"
    assert _inv(db_session, i1).due == 0


def test_admin_limit_is_cumulative_per_invoice(client, db_session):
    client.put("/settings", headers=OWNER_HEADERS, json={"writeoff_admin_limit": 200})
    _, iid, _ = _due_invoice(client, db_session)
    assert client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 150, "reason": "a"}).json()["status"] == "APPLIED"
    second = client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 100, "reason": "b"}).json()
    assert second["status"] == "PENDING_OWNER"  # 150 + 100 is above 200, no splitting around the limit


def test_write_off_validation_and_roles(client, db_session):
    _, iid, _ = _due_invoice(client, db_session)
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.post(f"/invoices/{iid}/write-off", headers=h, json={"amount": 10, "reason": "x"}).status_code == 403
    assert client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 10, "reason": "  "}).status_code in (400, 422)
    assert client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 301, "reason": "x"}).status_code == 400
    assert client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 0, "reason": "x"}).status_code == 422
    assert client.post("/invoices/99999999/write-off", headers=ADMIN_HEADERS, json={"amount": 1, "reason": "x"}).status_code == 404
    assert _inv(db_session, iid).due == 300


def test_written_off_money_is_not_owed_again_after_a_line_cancellation(client, db_session):
    """compute_cancellation_outcome subtracts what was written off (the refund rule itself is unchanged)."""
    from backend.app.services.refund_service import compute_cancellation_outcome
    _, iid, _ = _due_invoice(client, db_session)
    client.post(f"/invoices/{iid}/write-off", headers=OWNER_HEADERS, json={"amount": 100, "reason": "r"})
    inv = _inv(db_session, iid)
    line = inv.lines[0]
    out = compute_cancellation_outcome(inv, line)
    assert out["due_after"] == 0  # the only line is removed: nothing is owed


# ---------------------------------------------------------------- doctor balances (D43)
def test_doctor_balances_keep_the_two_kinds_apart(client, db_session):
    doc = _doctor(client)
    base = client.get("/doctor-balances", headers=ADMIN_HEADERS)
    assert base.status_code == 200 and "not built" in base.json()["note"]
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.get("/doctor-balances", headers=h).status_code == 403
    admin_id = ADMIN_HEADERS and db_session.execute(select(Invoice.created_by_id).limit(1)).scalar()
    db_session.add_all([
        DoctorBalanceEntry(tenant_id="center-seba-01", referrer_id=doc, kind="WHOLESALE_RECEIVABLE", amount=1000, source_type="TEST", created_by_id=admin_id),
        DoctorBalanceEntry(tenant_id="center-seba-01", referrer_id=doc, kind="WHOLESALE_RECEIVABLE", amount=-250, source_type="TEST", created_by_id=admin_id),
        DoctorBalanceEntry(tenant_id="center-seba-01", referrer_id=doc, kind="PROFESSIONAL_FEE_PAYABLE", amount=300, source_type="TEST", created_by_id=admin_id),
    ])
    db_session.commit()
    body = client.get("/doctor-balances", headers=OWNER_HEADERS).json()
    row = next(i for i in body["items"] if i["referrer_id"] == doc)
    assert row["wholesale_receivable"] == 750 and row["professional_fee_payable"] == 300
    assert not any(k in row for k in ("total", "net", "balance"))  # never one merged number
    assert body["entry_count"] >= 3

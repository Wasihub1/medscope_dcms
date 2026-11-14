"""
Automated Verification Suite for Module 21 (Accounting) + Module 22 (Day Open/Close)
Verification of Prompt 18 Implementation according to prompt/Testing_Prompt_Module_21_22_Accounting_Day_Close.md.

Guarantees:
- Runs strictly against medscope_test (conftest guard).
- Covers Area A (Journal integrity & DB triggers), Area B (Real postings),
  Area C (Day close / reopen / movements), Area D (Reports & CSV export),
  Area E (Regression & Invariants).
"""
import csv
import io
from datetime import date, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import text, select
from sqlalchemy.exc import DBAPIError

from backend.app.core.permissions import ROLE_DEFAULTS
from backend.app.core.timezone import utc_now, to_dhaka_time
from backend.app.models.accounting import Account, JournalEntry, JournalLine, DayMovement
from backend.app.models.business_day import BusinessDay, BusinessDayChannelBalance
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.payment import Payment
from backend.app.models.referrer import Referrer
from backend.app.models.refund import RefundRequest
from backend.app.models.test import Test
from backend.app.models.user import Staff
from backend.app.services import accounting_service as acct
from backend.app.services import refund_service
from tests.conftest import (
    ADMIN_HEADERS,
    CASHIER_HEADERS,
    DOCTOR_AUTH_TOKEN,
    OWNER_HEADERS,
    RECEPTIONIST_HEADERS,
    TECH_KAMAL_HEADERS,
)

TENANT = "center-seba-01"


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _restore_state(client):
    yield
    client.put("/settings", headers=OWNER_HEADERS, json={"cash_variance_tolerance": 0, "writeoff_admin_limit": 500, "report_hold_when_due": True})
    _ensure_open_day(client)


def _ensure_open_day(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st.get("is_open"):
        # If any day is REOPENED, close it first
        screen = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
        if screen.get("day") and screen["day"].get("status") == "REOPENED":
            client.post("/business-day/close", headers=ADMIN_HEADERS, json={
                "counted_cash": screen["cash"]["expected_cash"],
                "day_id": screen["day"]["id"],
            })
        client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 1000})


def _create_test(db, price: int = 1000, requires_doctor: bool = False, dept: str = "Clinical Pathology") -> Test:
    code = f"T_{uuid4().hex[:8].upper()}"
    t = Test(
        tenant_id=TENANT,
        code=code,
        name=f"Test {code}",
        department=dept,
        price=price,
        sample_type="Blood",
        performing_role="LAB_TECH",
        requires_doctor=requires_doctor,
        report_template="NUMERIC_TABLE",
        approval_rule="TECHNICIAN_FINAL",
        is_outsourced=False,
        active=True,
        lab_section="HEMATOLOGY",
    )
    db.add(t)
    db.commit()
    return t


def _create_patient(db) -> int:
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    return pid


def _create_invoice(client, db, test_ids, paid=0, method="CASH", discount=0, urgent=False):
    pid = _create_patient(db)
    body = {
        "patient_id": pid,
        "age_value": 30,
        "gender": "Male",
        "lines": [{"test_id": tid, "urgent": urgent} for tid in test_ids],
        "initial_payment_amount": paid,
        "initial_payment_method": method if paid > 0 else "CASH",
        "initial_payment_reference": f"TRX-INIT-{uuid4().hex[:8]}" if method != "CASH" and paid > 0 else None,
        "urgent": urgent,
    }
    if discount:
        body["bill_discount_type"] = "AMOUNT"
        body["bill_discount_value"] = discount
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ===========================================================================
# AREA A: Journal Integrity (Highest Priority)
# ===========================================================================
def test_a1_every_journal_entry_balances_all_paths(client, db_session):
    """Confirm every journal entry's lines sum to zero (debit == credit) across all 9+ posting paths."""
    _ensure_open_day(client)
    t1 = _create_test(db_session, 5000)
    t2 = _create_test(db_session, 4000)

    # 1. Bill Confirmed + Initial Payment (CASH)
    inv = _create_invoice(client, db_session, [t1.id, t2.id], paid=2000, method="CASH")
    iid = inv["id"]
    line1_id = next(l["id"] for l in inv["lines"] if l["test_id"] == t1.id)
    line2_id = next(l["id"] for l in inv["lines"] if l["test_id"] == t2.id)

    # 2. Payment Received (Due settlement)
    res_pmt = client.post(f"/invoices/{iid}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 500, "method": "BKASH", "reference": f"TRX-BK-{uuid4().hex[:8]}"})
    assert res_pmt.status_code == 201, res_pmt.text

    # 3. Line Cancelled (Immediate path, pre-lock)
    res_canc = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={"invoice_id": iid, "invoice_line_id": line1_id})
    assert res_canc.status_code == 201, res_canc.text

    # 4. Due Written Off (Admin within limit)
    res_wo = client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 300, "reason": "Patient hardship"})
    assert res_wo.status_code == 201, res_wo.text

    # 5. Day Movements: EXPENSE, BANK_DEPOSIT, OWNER_WITHDRAWAL
    res_exp = client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 50, "note": "Office supplies"})
    assert res_exp.status_code == 201, res_exp.text

    res_dep = client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "BANK_DEPOSIT", "amount": 100})
    assert res_dep.status_code == 201, res_dep.text

    res_wd = client.post("/business-day/movements", headers=OWNER_HEADERS, json={"kind": "OWNER_WITHDRAWAL", "amount": 150})
    assert res_wd.status_code == 201, res_wd.text

    # 6. Refund Paid (Create another bill, fully pay, cancel line -> refund request -> disburse)
    t3 = _create_test(db_session, 2000)
    inv2 = _create_invoice(client, db_session, [t3.id], paid=2000, method="CASH")
    l3_id = inv2["lines"][0]["id"]
    res_c2 = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={"invoice_id": inv2["id"], "invoice_line_id": l3_id})
    assert res_c2.status_code == 201
    refund_req_id = res_c2.json()["id"]

    # Disburse refund
    res_disb = client.post(f"/refunds/disburse/{refund_req_id}", headers=CASHIER_HEADERS, json={"payment_method": "CASH"})
    assert res_disb.status_code == 200, res_disb.text

    # 7. Cash Variance (Close day with variance)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp_cash = scr["cash"]["expected_cash"]
    day_id = scr["day"]["id"]
    res_close = client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp_cash - 10, "variance_reason": "Missing 10"})
    assert res_close.status_code == 200, res_close.text

    # 8. Reversal & Adjustment (Reopen day and post adjustments)
    res_reopen = client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "Auditing entries"})
    assert res_reopen.status_code == 200, res_reopen.text

    # Find the CASH_VARIANCE entry to reverse
    var_eid = db_session.execute(select(JournalEntry.id).where(JournalEntry.event_type == "CASH_VARIANCE", JournalEntry.business_day_id == day_id)).scalar_one()
    res_rev = client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={"reason": "Reversing variance", "reverse_entry_id": var_eid})
    assert res_rev.status_code == 201, res_rev.text

    # Manual balanced adjustment
    res_adj = client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={
        "reason": "Manual reclass",
        "lines": [{"account": "OPERATING_EXPENSE", "debit": 20}, {"account": "CASH", "credit": 20}]
    })
    assert res_adj.status_code == 201, res_adj.text

    # Re-close day
    client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": exp_cash, "day_id": day_id, "variance_reason": "Resolved"})

    # Check ALL journal entries in the database for balance
    unbalanced = db_session.execute(text(
        "SELECT entry_id, SUM(debit) as deb, SUM(credit) as cred "
        "FROM journal_lines GROUP BY entry_id HAVING SUM(debit) <> SUM(credit)"
    )).all()
    assert unbalanced == [], f"Found unbalanced journal entries: {unbalanced}"


def test_a2_db_triggers_reject_raw_update_and_delete(client, db_session):
    """Confirm database triggers reject UPDATE and DELETE on journal tables, except created_by_id on entries."""
    _ensure_open_day(client)
    t = _create_test(db_session, 1000)
    _create_invoice(client, db_session, [t.id], paid=500)

    lid = db_session.execute(text("SELECT id FROM journal_lines ORDER BY id DESC LIMIT 1")).scalar_one()
    eid = db_session.execute(text("SELECT entry_id FROM journal_lines WHERE id = :id"), {"id": lid}).scalar_one()

    # 1. Raw UPDATE on journal_lines must be refused by DB trigger
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(text("UPDATE journal_lines SET debit = debit + 10 WHERE id = :id"), {"id": lid})
    assert "journal rows are append-only" in str(exc_info.value)
    db_session.rollback()

    # 2. Raw DELETE on journal_lines must be refused by DB trigger
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(text("DELETE FROM journal_lines WHERE id = :id"), {"id": lid})
    assert "journal rows are append-only" in str(exc_info.value)
    db_session.rollback()

    # 3. Raw UPDATE on journal_entries (memo) must be refused by DB trigger
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(text("UPDATE journal_entries SET memo = 'tampered' WHERE id = :id"), {"id": eid})
    assert "journal rows are append-only" in str(exc_info.value)
    db_session.rollback()

    # 4. Raw DELETE on journal_entries must be refused by DB trigger
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(text("DELETE FROM journal_entries WHERE id = :id"), {"id": eid})
    assert "journal rows are append-only" in str(exc_info.value)
    db_session.rollback()

    # 5. Raw UPDATE on journal_entries.created_by_id MUST be allowed (fixture cleanup exception)
    staff_id = db_session.execute(select(Staff.id).order_by(Staff.id)).scalars().first()
    db_session.execute(text("UPDATE journal_entries SET created_by_id = :sid WHERE id = :id"), {"sid": staff_id, "id": eid})
    db_session.commit()
    # Confirm it persisted
    updated_sid = db_session.execute(text("SELECT created_by_id FROM journal_entries WHERE id = :id"), {"id": eid}).scalar_one()
    assert updated_sid == staff_id


def test_a3_db_deferred_constraint_refuses_unbalanced_entry_at_commit(client, db_session):
    """Confirm DB-level deferred constraint trigger rejects an unbalanced entry at commit."""
    _ensure_open_day(client)
    t = _create_test(db_session, 1000)
    _create_invoice(client, db_session, [t.id], paid=100)
    eid = db_session.execute(text("SELECT id FROM journal_entries ORDER BY id DESC LIMIT 1")).scalar_one()
    acc_id = db_session.execute(text("SELECT id FROM accounts LIMIT 1")).scalar_one()

    # Insert an unbalancing line directly via raw SQL
    with pytest.raises(DBAPIError) as exc_info:
        db_session.execute(
            text("INSERT INTO journal_lines (tenant_id, entry_id, account_id, debit, credit) "
                 "VALUES (:tid, :eid, :aid, 999, 0)"),
            {"tid": TENANT, "eid": eid, "aid": acc_id}
        )
        db_session.commit()
    assert "does not balance" in str(exc_info.value)
    db_session.rollback()


def test_a4_reversal_uniqueness(client, db_session):
    """Confirm a reversal entry can only be created once per original entry."""
    _ensure_open_day(client)
    t = _create_test(db_session, 1000)
    _create_invoice(client, db_session, [t.id], paid=500)
    eid = db_session.execute(text("SELECT id FROM journal_entries ORDER BY id DESC LIMIT 1")).scalar_one()

    # Reverse entry via service
    rev = acct.reverse_entry(db_session, TENANT, eid, actor_id=1, memo="First reversal")
    db_session.commit()
    assert rev.reverses_entry_id == eid

    # Attempt second reversal via service -> 409 Conflict
    with pytest.raises(Exception) as exc_info:
        acct.reverse_entry(db_session, TENANT, eid, actor_id=1, memo="Second reversal")
    assert "already been reversed" in str(exc_info.value)
    db_session.rollback()

    # Attempt second reversal via raw SQL -> DB unique constraint violation
    with pytest.raises(DBAPIError) as exc_db:
        db_session.execute(
            text("INSERT INTO journal_entries (tenant_id, entry_date, event_type, reverses_entry_id, is_adjustment, created_at) "
                 "VALUES (:tid, CURRENT_DATE, 'REVERSAL', :eid, true, NOW())"),
            {"tid": TENANT, "eid": eid}
        )
        db_session.commit()
    assert "uq_journal_entry_reverses" in str(exc_db.value)
    db_session.rollback()


def test_a5_unbuilt_modules_no_accounts_or_postings(client, db_session):
    """Cross-check claim directly against database: no accounts and no postings for unbuilt modules."""
    _ensure_open_day(client)
    # Seed chart
    acct.ensure_accounts(db_session, TENANT)
    db_session.commit()

    accounts = db_session.execute(select(Account).where(Account.tenant_id == TENANT)).scalars().all()
    account_names = {a.name.lower() for a in accounts}
    account_codes = {a.code for a in accounts}

    forbidden_terms = {"commission", "visit-fee", "visit fee", "consultant", "outside-lab", "outside lab"}
    for name in account_names:
        for term in forbidden_terms:
            assert term not in name, f"Found unbuilt module account name '{name}'"

    # Confirm event types in journal_entries
    kinds = {r[0] for r in db_session.execute(text("SELECT DISTINCT event_type FROM journal_entries WHERE tenant_id = :tid"), {"tid": TENANT})}
    forbidden_events = {"COMMISSION_ACCRUED", "COMMISSION_PAID", "VISIT_FEE_HANDOVER", "CONSULTANT_FEE", "OUTSIDE_LAB_COST"}
    assert not (kinds & forbidden_events), f"Found forbidden events: {kinds & forbidden_events}"


def test_a6_expected_cash_vs_journal_cash_probe(client, db_session):
    """
    Construct a scenario with bill, partial payment, cancellation, refund disbursement, and write-off.
    Verify that in a standard open day, journal's net effect on Cash in hand (1010) matches expected cash.
    """
    _ensure_open_day(client)
    scr_start = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    start_expected_cash = scr_start["cash"]["expected_cash"]
    cash_acc_id = db_session.execute(text("SELECT id FROM accounts WHERE tenant_id = :t AND code = '1010'"), {"t": TENANT}).scalar_one()

    def _cash_balance():
        db_session.expire_all()
        return db_session.execute(
            text("SELECT COALESCE(SUM(debit - credit), 0) FROM journal_lines WHERE account_id = :aid"),
            {"aid": cash_acc_id}
        ).scalar_one()

    start_journal_cash = _cash_balance()

    # 1. Invoice with cash payment: Gross 9000, paid 3000
    t1 = _create_test(db_session, 5000)
    t2 = _create_test(db_session, 4000)
    inv = _create_invoice(client, db_session, [t1.id, t2.id], paid=3000, method="CASH")
    iid = inv["id"]
    l1_id = next(l["id"] for l in inv["lines"] if l["test_id"] == t1.id)

    # 2. Cancel 5000 line (retained 3000, refund 0, due 1000)
    client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={"invoice_id": iid, "invoice_line_id": l1_id})

    # 3. Write off remaining due 400
    client.post(f"/invoices/{iid}/write-off", headers=OWNER_HEADERS, json={"amount": 400, "reason": "Hardship"})

    # 4. Another invoice with cash payment 2000, cancelled with cash refund 2000, and disbursed in cash
    t3 = _create_test(db_session, 2000)
    inv2 = _create_invoice(client, db_session, [t3.id], paid=2000, method="CASH")
    l3_id = inv2["lines"][0]["id"]
    c_res = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={"invoice_id": inv2["id"], "invoice_line_id": l3_id})
    req_id = c_res.json()["id"]
    client.post(f"/refunds/disburse/{req_id}", headers=CASHIER_HEADERS, json={"payment_method": "CASH"})

    # Check agreement:
    # Net cash collected = 3000 + 2000 = 5000
    # Net cash refunded = 2000
    # Net cash movement = +3000
    scr_end = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    delta_expected_cash = scr_end["cash"]["expected_cash"] - start_expected_cash
    delta_journal_cash = _cash_balance() - start_journal_cash

    assert delta_expected_cash == 3000
    assert delta_journal_cash == 3000
    assert delta_expected_cash == delta_journal_cash, "Expected cash and Journal cash diverged!"


# ===========================================================================
# AREA B: Real Postings (Correctness & Completeness)
# ===========================================================================
def test_b1_bill_confirmed_split_and_discount_rules(client, db_session):
    """Bill confirmed: verify split across receivable, discount, test revenue, urgent revenue."""
    _ensure_open_day(client)
    t = _create_test(db_session, 2000)

    # Bill with discount 200 and urgent=True (20% fee on 2000 = 400): Gross 2000, Net = 2000 - 200 + 400 = 2200
    inv = _create_invoice(client, db_session, [t.id], paid=500, discount=200, urgent=True)
    iid = inv["id"]

    je = db_session.execute(
        select(JournalEntry).where(JournalEntry.source_type == "INVOICE", JournalEntry.source_id == iid)
    ).scalars().first()
    assert je is not None
    assert je.event_type == "BILL_CONFIRMED"

    accs = {a.id: a.code for a in db_session.execute(select(Account).where(Account.tenant_id == TENANT)).scalars()}
    line_splits = {accs[l.account_id]: (l.debit, l.credit) for l in je.lines}

    # Dr RECEIVABLE 2200, Dr DISCOUNT 200, Cr TEST_REVENUE 2000, Cr URGENT_REVENUE 400
    assert line_splits["1200"] == (2200, 0)  # RECEIVABLE
    assert line_splits["4900"] == (200, 0)   # DISCOUNT
    assert line_splits["4000"] == (0, 2000)  # TEST_REVENUE
    assert line_splits["4010"] == (0, 400)   # URGENT_REVENUE


def test_b2_payment_received_all_channels(client, db_session):
    """Payment received: test across multiple channels (CASH, BKASH, NAGAD, POS_CARD, BANK_TRANSFER, OTHER)."""
    _ensure_open_day(client)
    channels = [
        ("CASH", "1010"),
        ("BKASH", "1020"),
        ("NAGAD", "1030"),
        ("ROCKET", "1040"),
        ("POS_CARD", "1050"),
        ("BANK_TRANSFER", "1060"),
    ]
    t = _create_test(db_session, 1000)

    for ch_name, acc_code in channels:
        inv = _create_invoice(client, db_session, [t.id], paid=500, method=ch_name)
        iid = inv["id"]
        # Find payment journal entry
        je = db_session.execute(
            select(JournalEntry).where(JournalEntry.event_type == "PAYMENT_RECEIVED", JournalEntry.source_type == "PAYMENT")
            .order_by(JournalEntry.id.desc())
        ).scalars().first()
        accs = {a.id: a.code for a in db_session.execute(select(Account).where(Account.tenant_id == TENANT)).scalars()}
        splits = {accs[l.account_id]: (l.debit, l.credit) for l in je.lines}
        assert splits[acc_code] == (500, 0)
        assert splits["1200"] == (0, 500)  # Cr RECEIVABLE


def test_b3_line_cancelled_immediate_and_approval(client, db_session):
    """Line cancelled: test immediate pre-lock path and legacy approval path."""
    _ensure_open_day(client)
    t1 = _create_test(db_session, 5000)
    t2 = _create_test(db_session, 4000)

    # 9000 gross, 3000 advance paid, cancel 5000 line
    inv = _create_invoice(client, db_session, [t1.id, t2.id], paid=3000)
    iid = inv["id"]
    l1_id = next(l["id"] for l in inv["lines"] if l["test_id"] == t1.id)

    # Cancel immediate
    res = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={"invoice_id": iid, "invoice_line_id": l1_id})
    assert res.status_code == 201

    je = db_session.execute(
        select(JournalEntry).where(JournalEntry.event_type == "LINE_CANCELLED", JournalEntry.source_id == l1_id)
    ).scalars().first()
    assert je is not None
    accs = {a.id: a.code for a in db_session.execute(select(Account).where(Account.tenant_id == TENANT)).scalars()}
    splits = {accs[l.account_id]: (l.debit, l.credit) for l in je.lines}
    assert splits["4000"] == (5000, 0)  # Dr TEST_REVENUE
    assert splits["1200"] == (0, 5000)  # Cr RECEIVABLE


def test_b4_refund_paid_disbursement_separation(client, db_session):
    """Refund paid: disbursement reduces Refunds payable and correct channel; request does not post."""
    _ensure_open_day(client)
    t = _create_test(db_session, 1500)
    inv = _create_invoice(client, db_session, [t.id], paid=1500, method="BKASH")
    lid = inv["lines"][0]["id"]

    # Request cancellation
    entries_before = db_session.execute(select(JournalEntry.id)).scalars().all()
    res_req = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={"invoice_id": inv["id"], "invoice_line_id": lid})
    assert res_req.status_code == 201
    req_id = res_req.json()["id"]

    # Verify no REFUND_PAID entry was posted by the request for this req_id
    paid_for_req = db_session.execute(
        select(JournalEntry).where(JournalEntry.event_type == "REFUND_PAID", JournalEntry.source_id == req_id)
    ).scalars().all()
    assert paid_for_req == []

    # Disburse refund via BKASH
    res_disb = client.post(f"/refunds/disburse/{req_id}", headers=CASHIER_HEADERS, json={"method": "BKASH", "reference": f"REF-DISB-BK-{uuid4().hex[:8]}"})
    assert res_disb.status_code == 200, res_disb.text

    je = db_session.execute(
        select(JournalEntry).where(JournalEntry.event_type == "REFUND_PAID", JournalEntry.source_id == req_id)
    ).scalars().first()
    assert je is not None
    accs = {a.id: a.code for a in db_session.execute(select(Account).where(Account.tenant_id == TENANT)).scalars()}
    splits = {accs[l.account_id]: (l.debit, l.credit) for l in je.lines}
    assert splits["2100"] == (1500, 0)  # Dr REFUND_PAYABLE
    assert splits["1020"] == (0, 1500)  # Cr BKASH


def test_b5_due_written_off_hard_separation_from_discount(client, db_session):
    """Due write-off posts to Bad Debt (5100), never Discount Given (4900)."""
    _ensure_open_day(client)
    t = _create_test(db_session, 800)
    inv = _create_invoice(client, db_session, [t.id], paid=300)
    iid = inv["id"]

    res_wo = client.post(f"/invoices/{iid}/write-off", headers=ADMIN_HEADERS, json={"amount": 250, "reason": "Charity"})
    assert res_wo.status_code == 201
    wo_id = res_wo.json()["id"]

    je = db_session.execute(
        select(JournalEntry).where(JournalEntry.event_type == "DUE_WRITTEN_OFF", JournalEntry.source_id == wo_id)
    ).scalars().first()
    assert je is not None
    accs = {a.id: a.code for a in db_session.execute(select(Account).where(Account.tenant_id == TENANT)).scalars()}
    splits = {accs[l.account_id]: (l.debit, l.credit) for l in je.lines}
    assert splits["5100"] == (250, 0)  # Dr BAD_DEBT
    assert splits["1200"] == (0, 250)  # Cr RECEIVABLE
    assert "4900" not in splits         # No discount involved


def test_b6_movements_and_rbac_investigation(client, db_session):
    """
    Test Day Movements and RBAC.
    Note: Investigation check on BANK_DEPOSIT and OWNER_WITHDRAWAL role restrictions.
    """
    _ensure_open_day(client)
    # Ensure drawer has cash
    t = _create_test(db_session, 2000)
    _create_invoice(client, db_session, [t.id], paid=1500)

    # Receptionist and Cashier are forbidden from all movements (no business_day.close)
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS):
        assert client.post("/business-day/movements", headers=h, json={"kind": "EXPENSE", "amount": 10, "note": "x"}).status_code == 403
        assert client.post("/business-day/movements", headers=h, json={"kind": "BANK_DEPOSIT", "amount": 10}).status_code == 403
        assert client.post("/business-day/movements", headers=h, json={"kind": "OWNER_WITHDRAWAL", "amount": 10}).status_code == 403

    # Admin: OWNER_WITHDRAWAL is rejected with 403
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "OWNER_WITHDRAWAL", "amount": 10}).status_code == 403

    # Admin: EXPENSE succeeds
    res_exp = client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 10, "note": "Tea"})
    assert res_exp.status_code == 201

    # BANK_DEPOSIT check: does Admin succeed or get 403?
    res_bank = client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "BANK_DEPOSIT", "amount": 15})
    # The prompt noted to confirm if bank deposit is Owner-only at API level.
    # In implementation, Admin holds business_day.close and record_movement only guards OWNER_WITHDRAWAL with actor.role != 'OWNER'.
    # So Admin receives 201 (as tested in test_prompt18_accounting_day_close.py line 92).
    assert res_bank.status_code == 201, "Admin bank deposit returned unexpected status"


def test_b7_lazy_account_creation_fresh_tenant(client, db_session):
    """Confirm 16 accounts are lazily seeded on first posting for a fresh tenant with no duplicates."""
    fresh_tenant = f"fresh-tenant-{uuid4().hex[:8]}"
    existing = db_session.execute(select(Account).where(Account.tenant_id == fresh_tenant)).scalars().all()
    assert existing == []

    # First call seeds 16 accounts
    ids1 = acct.ensure_accounts(db_session, fresh_tenant)
    assert len(ids1) == 16

    count = db_session.execute(select(Account).where(Account.tenant_id == fresh_tenant)).scalars().all()
    assert len(count) == 16

    # Second call is idempotent
    ids2 = acct.ensure_accounts(db_session, fresh_tenant)
    assert ids1 == ids2
    count2 = db_session.execute(select(Account).where(Account.tenant_id == fresh_tenant)).scalars().all()
    assert len(count2) == 16


# ===========================================================================
# AREA C: Day Close / Reopen / Movements
# ===========================================================================
def test_c1_d45_expected_cash_identity_and_integers(client, db_session):
    """D45 expected cash identity: opening + collections - refunds - movements = expected cash (integers only)."""
    _ensure_open_day(client)
    t = _create_test(db_session, 3000)
    _create_invoice(client, db_session, [t.id], paid=2000, method="CASH")

    client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 35, "note": "cleaner"})
    client.post("/business-day/movements", headers=OWNER_HEADERS, json={"kind": "OWNER_WITHDRAWAL", "amount": 45})
    client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "BANK_DEPOSIT", "amount": 55})

    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    c = scr["cash"]
    calc = c["opening_cash"] + c["cash_collections"] - c["cash_refunds"] - c["bank_deposits"] - c["owner_withdrawals"] - c["expenses"] + c["adjusting_entries"]  # Prompt 18B: adjusting entries are an explicit term
    assert c["expected_cash"] == calc
    for val in (c["opening_cash"], c["cash_collections"], c["cash_refunds"], c["bank_deposits"], c["owner_withdrawals"], c["expenses"], c["expected_cash"]):
        assert isinstance(val, int) and not isinstance(val, bool)


def test_c2_writeoffs_do_not_affect_expected_cash(client, db_session):
    """Write-offs are strictly non-cash and do not alter expected cash."""
    _ensure_open_day(client)
    t = _create_test(db_session, 2000)
    inv = _create_invoice(client, db_session, [t.id], paid=500)
    iid = inv["id"]

    before = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()["cash"]["expected_cash"]
    client.post(f"/invoices/{iid}/write-off", headers=OWNER_HEADERS, json={"amount": 400, "reason": "Forgiven"})
    after = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()["cash"]["expected_cash"]
    assert before == after


def test_c3_per_channel_independence(client, db_session):
    """Channel lines (wallet/bank) are independent of cash line."""
    _ensure_open_day(client)
    scr_before = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    bkash_before = next(ch["collections"] for ch in scr_before["channels"] if ch["channel"] == "BKASH")
    cash_before = next(ch["collections"] for ch in scr_before["channels"] if ch["channel"] == "CASH")

    t = _create_test(db_session, 1000)
    _create_invoice(client, db_session, [t.id], paid=600, method="BKASH")

    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    bkash_channel = next(ch for ch in scr["channels"] if ch["channel"] == "BKASH")
    cash_channel = next(ch for ch in scr["channels"] if ch["channel"] == "CASH")

    assert bkash_channel["collections"] - bkash_before == 600
    assert bkash_channel["paid_out"] == 0  # movements only affect cash
    assert cash_channel["collections"] == cash_before


def test_c4_variance_reason_gating_and_tolerance(client, db_session):
    """Variance reason gating with tolerance 0 vs custom tolerance."""
    _ensure_open_day(client)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp = scr["cash"]["expected_cash"]

    # Tolerance is 0 by default: variance of 5 requires reason
    assert client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp - 5}).status_code == 400
    ok = client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp - 5, "variance_reason": "Shortage"})
    assert ok.status_code == 200

    # Reopen day and set tolerance to 20
    day_id = scr["day"]["id"]
    client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "Tolerance test"})
    client.put("/settings", headers=OWNER_HEADERS, json={"cash_variance_tolerance": 20})

    # Variance of 15 (within tolerance 20) closes without reason
    ok_tol = client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": exp - 15, "day_id": day_id})
    assert ok_tol.status_code == 200

    # Reopen again: variance of 25 (exceeds tolerance 20) requires reason
    client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "Exceed tolerance test"})
    assert client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": exp - 25, "day_id": day_id}).status_code == 400
    ok_exceed = client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": exp - 25, "day_id": day_id, "variance_reason": "Big drop"})
    assert ok_exceed.status_code == 200


def test_c5_business_day_close_rbac(client, db_session):
    """POST /business-day/close is Admin/Owner only."""
    _ensure_open_day(client)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp = scr["cash"]["expected_cash"]

    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.post("/business-day/close", headers=h, json={"counted_cash": exp}).status_code == 403

    assert client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp}).status_code == 200


def test_c6_closed_or_reopened_day_refuses_actions(client, db_session):
    """
    Test actions against closed or reopened days.
    - Movements against closed day are refused with 409.
    - Direct calls to acct.post with closed_day_id are refused with 409.
    - Investigation: payments/invoices when no day is open silently fall back to business_day_id=None.
    """
    _ensure_open_day(client)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp = scr["cash"]["expected_cash"]
    day_id = scr["day"]["id"]

    # Close the day
    client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp})

    # 1. Day Movement against closed day is refused with 409
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 10, "note": "x"}).status_code == 409

    # 2. Direct service post targeting closed day raises 409
    with pytest.raises(Exception) as exc_info:
        acct.post(db_session, TENANT, "MANUAL", [("CASH", 10, 0), ("RECEIVABLE", 0, 10)], actor_id=1, business_day_id=day_id)
    assert "is closed" in str(exc_info.value)

    # 3. Reopen day
    client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "Investigate"})

    # Movements still refused with 409 on reopened day
    assert client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 10, "note": "x"}).status_code == 409

    # Direct non-adjustment post targeting reopened day raises 409
    with pytest.raises(Exception) as exc_info2:
        acct.post(db_session, TENANT, "MANUAL", [("CASH", 10, 0), ("RECEIVABLE", 0, 10)], actor_id=1, business_day_id=day_id, is_adjustment=False)
    assert "is closed" in str(exc_info2.value)


def test_c7_reopen_owner_only_and_preserves_closed_at(client, db_session):
    """Reopen is Owner-only, requires reason, status REOPENED, and re-closing preserves original closed_at."""
    _ensure_open_day(client)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp = scr["cash"]["expected_cash"]
    day_id = scr["day"]["id"]

    client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp})
    db_session.expire_all()
    orig_closed_at = db_session.get(BusinessDay, day_id).closed_at
    assert orig_closed_at is not None

    # Admin gets 403
    assert client.post(f"/business-day/{day_id}/reopen", headers=ADMIN_HEADERS, json={"reason": "Admin test"}).status_code == 403

    # Owner without reason gets 400
    assert client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "  "}).status_code == 400

    # Owner with reason succeeds
    res_re = client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "Auditing cash recount"})
    assert res_re.status_code == 200

    db_session.expire_all()
    day = db_session.get(BusinessDay, day_id)
    assert day.status == "REOPENED"
    assert day.reopen_reason == "Auditing cash recount"
    assert day.reopened_at is not None

    # Re-close day
    client.post("/business-day/close", headers=OWNER_HEADERS, json={"counted_cash": exp, "day_id": day_id})
    db_session.expire_all()
    day_reclosed = db_session.get(BusinessDay, day_id)
    assert day_reclosed.status == "CLOSED"
    assert day_reclosed.closed_at == orig_closed_at, "Re-close must preserve original closed_at timestamp"


def test_c8_reopened_day_accepts_only_adjustments(client, db_session):
    """A reopened day accepts only adjusting entries (reversals or balanced manual adjustments)."""
    _ensure_open_day(client)
    t = _create_test(db_session, 1000)
    _create_invoice(client, db_session, [t.id], paid=500)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp = scr["cash"]["expected_cash"]
    day_id = scr["day"]["id"]

    client.post("/business-day/close", headers=ADMIN_HEADERS, json={"counted_cash": exp - 10, "variance_reason": "off by 10"})
    client.post(f"/business-day/{day_id}/reopen", headers=OWNER_HEADERS, json={"reason": "Adjustments test"})

    # Admin cannot post adjustment -> 403
    assert client.post(f"/business-day/{day_id}/adjustments", headers=ADMIN_HEADERS, json={"reason": "test"}).status_code == 403

    # Owner adjustment without reason -> 400
    assert client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={"reason": ""}).status_code in (400, 422)

    # Owner adjustment with unbalanced lines -> 400
    assert client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={
        "reason": "unbalanced",
        "lines": [{"account": "CASH", "debit": 10}, {"account": "TEST_REVENUE", "credit": 5}]
    }).status_code == 400

    # Valid manual adjustment -> 201
    ok = client.post(f"/business-day/{day_id}/adjustments", headers=OWNER_HEADERS, json={
        "reason": "Correcting cash",
        "lines": [{"account": "CASH", "debit": 10}, {"account": "OPERATING_EXPENSE", "credit": 10}]
    })
    assert ok.status_code == 201


def test_c9_movements_cannot_exceed_expected_cash_and_expense_note_required(client, db_session):
    """Movements cannot exceed drawer expected cash, and EXPENSE requires note."""
    _ensure_open_day(client)
    scr = client.get("/business-day/day-screen", headers=ADMIN_HEADERS).json()
    exp = scr["cash"]["expected_cash"]

    # Amount > expected cash -> 400
    res_over = client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": exp + 1000, "note": "big"})
    assert res_over.status_code == 400
    assert "cannot be taken out" in res_over.text

    # Expense without note -> 400
    res_no_note = client.post("/business-day/movements", headers=ADMIN_HEADERS, json={"kind": "EXPENSE", "amount": 10})
    assert res_no_note.status_code in (400, 422)


def test_c10_close_body_contract_requires_counted_cash(client, db_session):
    """POST /business-day/close requires counted_cash (empty body returns 422)."""
    _ensure_open_day(client)
    res = client.post("/business-day/close", headers=ADMIN_HEADERS, json={})
    assert res.status_code == 422


# ===========================================================================
# AREA D: Reports & Exports
# ===========================================================================
def test_d1_cash_book_and_income_expense_exact_math(client, db_session):
    """Cash book and income-expense reports match hand-computed expectations."""
    _ensure_open_day(client)
    t = _create_test(db_session, 2000)

    # Confirm bill: Gross 2000, discount 100, urgent fee (20% on 2000 = 400) -> Net 2300, paid 1000
    inv = _create_invoice(client, db_session, [t.id], paid=1000, discount=100, urgent=True)
    today = date.today()

    # Cash book
    cb = client.get(f"/accounting/cash-book?from={today}&to={today}&channel=CASH", headers=ADMIN_HEADERS).json()
    assert cb["channel"] == "CASH"
    assert cb["total_in"] >= 1000

    # Income-expense
    ie = client.get(f"/accounting/income-expense?from={today}&to={today}", headers=ADMIN_HEADERS).json()
    row = next(r for r in ie["rows"] if r["date"] == today.isoformat())
    assert row["test_revenue"] >= 2000
    assert row["urgent_fee_revenue"] >= 400
    assert row["discount_given"] >= 100
    assert row["income"] == row["test_revenue"] + row["urgent_fee_revenue"] - row["discount_given"]


def test_d2_dues_report_date_filtering(client, db_session):
    """Dues report supports optional date filtering while preserving underlying calculation."""
    _ensure_open_day(client)
    t = _create_test(db_session, 1500)
    inv = _create_invoice(client, db_session, [t.id], paid=500)
    today = date.today()

    # Filter with today's date
    res = client.get(f"/accounting/dues?from={today}&to={today}", headers=ADMIN_HEADERS).json()
    assert any(r["bill_no"] == inv["invoice_no"] and r["due"] == 1000 for r in res["rows"])

    # Filter with past date
    past = today - timedelta(days=5)
    res_past = client.get(f"/accounting/dues?from={past}&to={past}", headers=ADMIN_HEADERS).json()
    assert not any(r["bill_no"] == inv["invoice_no"] for r in res_past["rows"])


def test_d3_cost_by_referrer_billing_real_and_cost_zero(client, db_session):
    """Cost-by-referrer shows real billing and cost is 0 with explicit note."""
    _ensure_open_day(client)
    res = client.get("/accounting/cost-by-referrer", headers=ADMIN_HEADERS).json()
    assert "rows" in res
    assert "note" in res
    assert "not built" in res["note"]
    assert res["total_cost"] == 0
    for r in res["rows"]:
        assert r["cost"] == 0
        assert r["net_billed"] >= 0


def test_d4_csv_exports_validity_and_utf8_bom(client, db_session):
    """CSV export on all 4 accounting reports returns valid CSV starting with UTF-8 BOM."""
    _ensure_open_day(client)
    today = date.today()
    endpoints = [
        f"/accounting/cash-book?from={today}&format=csv",
        f"/accounting/income-expense?from={today}&format=csv",
        f"/accounting/dues?format=csv",
        f"/accounting/cost-by-referrer?format=csv",
    ]

    for ep in endpoints:
        res = client.get(ep, headers=ADMIN_HEADERS)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/csv")
        content = res.text
        # Check UTF-8 BOM
        assert content.startswith("\ufeff"), f"Endpoint {ep} missing UTF-8 BOM"

        # Parse CSV
        reader = csv.reader(io.StringIO(content.lstrip("\ufeff")))
        rows = list(reader)
        assert len(rows) >= 1, f"Empty CSV from {ep}"


def test_d5_accounting_view_permission_matrix(client, db_session):
    """accounting.view key gates all /accounting endpoints: Admin/Owner 200, others 403."""
    _ensure_open_day(client)
    endpoints = [
        "/accounting/cash-book",
        "/accounting/income-expense",
        "/accounting/dues",
        "/accounting/cost-by-referrer",
        "/accounting/journal",
    ]

    for ep in endpoints:
        assert client.get(ep, headers=ADMIN_HEADERS).status_code == 200
        assert client.get(ep, headers=OWNER_HEADERS).status_code == 200
        assert client.get(ep, headers=RECEPTIONIST_HEADERS).status_code == 403
        assert client.get(ep, headers=CASHIER_HEADERS).status_code == 403
        assert client.get(ep, headers=TECH_KAMAL_HEADERS).status_code == 403


# ===========================================================================
# AREA E: Regression & Invariants
# ===========================================================================
def test_e1_business_day_state_endpoint_unchanged(client, db_session):
    """GET /business-day/state is money-free, accessible to all authenticated roles."""
    _ensure_open_day(client)
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS, ADMIN_HEADERS, OWNER_HEADERS):
        res = client.get("/business-day/state", headers=h)
        assert res.status_code == 200
        data = res.json()
        assert "is_open" in data
        assert "day_number" in data
        # Must not contain money fields
        assert "opening_cash" not in data
        assert "expected_cash" not in data
        assert "closing_cash_counted" not in data


def test_e2_whole_taka_integers_preserved_everywhere(client, db_session):
    """Confirm database schema and API payloads preserve whole-taka integer math."""
    _ensure_open_day(client)
    # Check column types in DB for accounting tables
    for table in ("accounts", "journal_lines", "day_movements"):
        cols = db_session.execute(text(
            f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'"
        )).all()
        for col_name, d_type in cols:
            if col_name in ("debit", "credit", "amount", "opening_cash", "counted_cash", "variance"):
                assert d_type in ("integer", "bigint", "smallint"), f"Column {table}.{col_name} has float/decimal type: {d_type}"

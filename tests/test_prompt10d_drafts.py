"""
Prompt 10D Part 3 — Invoice Draft / Finalize workflow.
- A DRAFT has no operational effect (no lines, orders, visit, payment, sequence number, drawer change).
- Finalize assigns the real invoice number and creates every confirmation side effect.
- Finalize is not repeatable; editing after finalize is blocked.
"""
from sqlalchemy import select, func

from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.payment import Payment
from backend.app.models.test import Test
from backend.app.models.test_order import TestOrder
from backend.app.models.audit import AuditLog
from tests.conftest import RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS


def _ids(db):
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    hgb = db.execute(select(Test.id).where(Test.code == "HGB")).scalar_one()
    rbs = db.execute(select(Test.id).where(Test.code == "RBS")).scalar_one()
    return pid, hgb, rbs


def _payload(db, paid=0):
    pid, hgb, rbs = _ids(db)
    return {
        "patient_id": pid,
        "age_value": 35,  # Prompt 10E: Finalize requires age and gender
        "gender": "Male",
        "lines": [{"test_id": hgb}, {"test_id": rbs}],
        "initial_payment_amount": paid,
        "initial_payment_method": "CASH",
    }


def _counts(db):
    db.expire_all()
    return (
        db.execute(select(func.count(InvoiceLine.id))).scalar_one(),
        db.execute(select(func.count(TestOrder.id))).scalar_one(),
        db.execute(select(func.count(Payment.id))).scalar_one(),
    )


def test_draft_has_no_operational_side_effects(client, db_session):
    before = _counts(db_session)
    res = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=_payload(db_session, paid=100))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "DRAFT" and body["is_draft"] is True
    assert body["invoice_no"].startswith("DRAFT-")  # no invoice number consumed
    assert body["visit_id"] is None
    assert body["lines"] == [] and body["payments"] == []
    assert body["paid"] == 0 and body["due"] == 0
    assert body["net"] == 300  # display total only
    assert body["draft_payload"]["initial_payment_amount"] == 100
    assert _counts(db_session) == before  # no lines, orders or payments

    # Not visible in dues, and not in technician worklists
    dues = client.get("/dues", headers=RECEPTIONIST_HEADERS).json()
    assert all(d.get("id") != body["id"] for d in dues)
    wl = client.get("/worklist", headers=TECH_KAMAL_HEADERS).json()
    assert all(i.get("invoice_no") != body["invoice_no"] for i in wl)

    # Invoice list shows it as Draft; payment filters exclude it
    drafts = client.get("/invoices?status=Draft", headers=RECEPTIONIST_HEADERS).json()
    assert any(i["id"] == body["id"] and i["is_draft"] for i in drafts)
    unpaid = client.get("/invoices?status=Unpaid&limit=200", headers=RECEPTIONIST_HEADERS).json()
    assert all(i["id"] != body["id"] for i in unpaid)

    # Payments and receipt printing are refused on a draft
    pay = client.post(f"/invoices/{body['id']}/settle-due", headers=RECEPTIONIST_HEADERS, json={"amount": 50, "method": "CASH"})
    assert pay.status_code == 400
    assert client.post(f"/invoices/{body['id']}/reprint", headers=RECEPTIONIST_HEADERS).status_code == 400


def test_draft_can_be_edited_then_finalized_with_side_effects(client, db_session):
    res = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=_payload(db_session))
    draft_id = res.json()["id"]

    upd_payload = _payload(db_session, paid=300)
    upd_payload["lines"] = upd_payload["lines"][:1] + [upd_payload["lines"][1]]
    upd = client.put(f"/invoices/{draft_id}/draft", headers=RECEPTIONIST_HEADERS, json=upd_payload)
    assert upd.status_code == 200, upd.text
    assert upd.json()["draft_payload"]["initial_payment_amount"] == 300

    before = _counts(db_session)
    fin = client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS)
    assert fin.status_code == 200, fin.text
    body = fin.json()
    assert body["id"] == draft_id
    assert body["status"] == "CONFIRMED" and body["is_draft"] is False
    assert body["invoice_no"].startswith("SD-")
    assert body["visit_id"] is not None and body["finalized_at"] is not None
    assert len(body["lines"]) == 2 and len(body["payments"]) == 1
    assert body["paid"] == 300 and body["due"] == 0
    after = _counts(db_session)
    assert after[0] == before[0] + 2 and after[1] == before[1] + 2 and after[2] == before[2] + 1

    db_session.expire_all()
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "INVOICE", AuditLog.entity_id == str(draft_id), AuditLog.action == "CONFIRM_INVOICE")
    ).scalars().all()
    assert len(audit) == 1


def test_finalize_is_not_repeatable_and_edits_after_finalize_blocked(client, db_session):
    draft_id = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=_payload(db_session)).json()["id"]
    assert client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS).status_code == 200
    again = client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS)
    assert again.status_code == 409
    edit = client.put(f"/invoices/{draft_id}/draft", headers=RECEPTIONIST_HEADERS, json=_payload(db_session))
    assert edit.status_code == 409
    db_session.expire_all()
    assert len(db_session.get(Invoice, draft_id).lines) == 2  # no duplicate lines from the second attempt


def test_direct_finalize_of_unsaved_form_still_works(client, db_session):
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_payload(db_session))
    assert res.status_code == 201
    assert res.json()["status"] == "CONFIRMED"
    assert res.json()["finalized_at"] is not None


def test_technician_cannot_create_or_finalize_drafts(client, db_session):
    assert client.post("/invoices/drafts", headers=TECH_KAMAL_HEADERS, json=_payload(db_session)).status_code == 403

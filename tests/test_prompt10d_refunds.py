"""
Refund amount on line cancellation — Prompt 10E Part 1 rule (replaces the Prompt 10D
proportional allocation, ADL-036 and assumptions A4/A6).

    net_after     = invoice net after removing the cancelled line's net price
    retained_paid = paid - all APPROVED and DISBURSED refunds so far
    refund        = max(0, retained_paid - net_after)
    due           = max(0, net_after - (retained_paid - refund))

A refund and a due never coexist after a cancellation; the sum of refunds never exceeds paid;
the urgent fee belongs to the invoice and is never refunded; client amounts are ignored.
Technicians never see refund amounts.
"""
from sqlalchemy import select

from backend.app.models.invoice import Invoice
from backend.app.models.patient import Patient
from backend.app.models.refund import RefundRequest
from backend.app.models.test import Test
from tests.conftest import RECEPTIONIST_HEADERS, ADMIN_HEADERS, TECH_KAMAL_HEADERS

# Seed catalog prices: TSH = 600 ("A"), CBC = 400 ("B"), HGB = 150 ("C")
A, B, C = "TSH", "CBC", "HGB"


def _test_id(db, code):
    return db.execute(select(Test.id).where(Test.code == code)).scalar_one()


def _patient_id(db):
    return db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()


def _create_invoice(client, db, codes, paid, urgent_codes=()):
    res = client.post(
        "/invoices",
        headers=RECEPTIONIST_HEADERS,
        json={
            "patient_id": _patient_id(db),
            "age_value": 35,
            "gender": "Male",
            "lines": [{"test_id": _test_id(db, c), "urgent": c in urgent_codes} for c in codes],
            "initial_payment_amount": paid,
            "initial_payment_method": "CASH",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _line_id(invoice_json, code):
    return next(l["id"] for l in invoice_json["lines"] if l["test_code_snapshot"] == code)


def _request_and_approve(client, invoice_json, code, amount=None):
    body = {"invoice_id": invoice_json["id"], "invoice_line_id": _line_id(invoice_json, code), "reason": "Patient left before sample"}
    if amount is not None:
        body["amount"] = amount
    req = client.post("/refunds", headers=RECEPTIONIST_HEADERS, json=body)
    assert req.status_code == 201, req.text
    req_id = req.json()["id"]
    # Prompt 13A: pre-lock cancellation takes effect immediately; there is no approval step any more.
    assert req.json()["status"] in ("APPROVED", "COMPLETED"), req.text
    return req_id


def _reload(db, invoice_id):
    db.expire_all()
    return db.get(Invoice, invoice_id)


def _amount(db, req_id):
    db.expire_all()
    return db.get(RefundRequest, req_id).amount


def _assert_no_refund_and_due_together(invoice):
    assert not (invoice.refund_due > 0 and invoice.due > 0)


def _case(client, db, paid, exp_refund, exp_due):
    inv = _create_invoice(client, db, [A, B], paid=paid)
    assert inv["net_amount"] == 1000
    req_id = _request_and_approve(client, inv, B)
    invoice = _reload(db, inv["id"])
    assert _amount(db, req_id) == exp_refund
    assert invoice.net == 600
    assert invoice.due == exp_due
    assert invoice.refund_due == exp_refund
    _assert_no_refund_and_due_together(invoice)
    return invoice, req_id


def test_worked_case_paid_500_refund_0_due_100(client, db_session):
    invoice, req_id = _case(client, db_session, 500, 0, 100)
    db_session.expire_all()
    assert db_session.get(RefundRequest, req_id).status == "COMPLETED"  # nothing to disburse
    assert invoice.payment_status == "PARTLY_PAID"


def test_worked_case_paid_800_refund_200_due_0(client, db_session):
    invoice, _ = _case(client, db_session, 800, 200, 0)
    assert invoice.refund_status == "REFUND_APPROVED"


def test_worked_case_paid_1000_refund_400_due_0_and_disburses(client, db_session):
    invoice, req_id = _case(client, db_session, 1000, 400, 0)
    dis = client.post(f"/refunds/disburse/{req_id}", headers=RECEPTIONIST_HEADERS, json={"method": "CASH"})
    assert dis.status_code == 200, dis.text
    invoice = _reload(db_session, invoice.id)
    assert invoice.refund_due == 0
    assert invoice.refund_status == "PARTIALLY_REFUNDED"


def test_worked_case_paid_0_refund_0_due_600(client, db_session):
    invoice, req_id = _case(client, db_session, 0, 0, 600)
    db_session.expire_all()
    assert db_session.get(RefundRequest, req_id).status == "COMPLETED"
    assert invoice.payment_status == "UNPAID"
    line = next(l for l in invoice.lines if l.test_code_snapshot == B)
    assert line.status == "CANCELLED"


def test_repeated_cancellations_on_one_invoice(client, db_session):
    # A 600 + B 400 + C 150 = 1150, paid 1000
    inv = _create_invoice(client, db_session, [A, B, C], paid=1000)
    r1 = _request_and_approve(client, inv, C)   # net_after 1000, retained 1000 -> refund 0
    i1 = _reload(db_session, inv["id"])
    assert _amount(db_session, r1) == 0 and i1.due == 0 and i1.net == 1000
    r2 = _request_and_approve(client, inv, B)   # net_after 600 -> refund 400
    i2 = _reload(db_session, inv["id"])
    assert _amount(db_session, r2) == 400 and i2.due == 0 and i2.net == 600
    r3 = _request_and_approve(client, inv, A)   # net_after 0, retained 600 -> refund 600
    i3 = _reload(db_session, inv["id"])
    assert _amount(db_session, r3) == 600 and i3.due == 0 and i3.net == 0
    total = sum(_amount(db_session, r) for r in (r1, r2, r3))
    assert total == 1000 == i3.paid  # never more than paid
    _assert_no_refund_and_due_together(i3)


def test_cancellation_after_an_earlier_disbursed_refund(client, db_session):
    inv = _create_invoice(client, db_session, [A, B], paid=1000)
    r1 = _request_and_approve(client, inv, B)
    assert _amount(db_session, r1) == 400
    assert client.post(f"/refunds/disburse/{r1}", headers=RECEPTIONIST_HEADERS, json={"method": "CASH"}).status_code == 200
    r2 = _request_and_approve(client, inv, A)  # retained = 1000 - 400 = 600, net_after 0 -> 600
    invoice = _reload(db_session, inv["id"])
    assert _amount(db_session, r2) == 600
    assert invoice.net == 0 and invoice.due == 0
    assert _amount(db_session, r1) + _amount(db_session, r2) == invoice.paid


def test_partial_payment_then_second_cancellation_turns_due_into_refund(client, db_session):
    inv = _create_invoice(client, db_session, [A, B], paid=500)
    r1 = _request_and_approve(client, inv, B)   # refund 0, due 100
    assert _amount(db_session, r1) == 0 and _reload(db_session, inv["id"]).due == 100
    r2 = _request_and_approve(client, inv, A)   # net_after 0 -> refund 500, due 0
    invoice = _reload(db_session, inv["id"])
    assert _amount(db_session, r2) == 500 and invoice.due == 0 and invoice.net == 0
    _assert_no_refund_and_due_together(invoice)


def test_client_supplied_amount_is_ignored(client, db_session):
    inv = _create_invoice(client, db_session, [A, B], paid=800)
    req_id = _request_and_approve(client, inv, B, amount=999)
    assert _amount(db_session, req_id) == 200


def test_urgent_fee_is_not_refunded_when_lines_are_cancelled(client, db_session):
    # A urgent: fee = max(100, 20% of 600) = 120; net = 600 + 400 + 120 = 1120, fully paid
    inv = _create_invoice(client, db_session, [A, B], paid=1120, urgent_codes=(A,))
    assert inv["urgent_fee"] == 120 and inv["net_amount"] == 1120
    r1 = _request_and_approve(client, inv, B)   # net_after 720 -> refund 400
    assert _amount(db_session, r1) == 400
    r2 = _request_and_approve(client, inv, A)   # net_after = fee 120 -> refund 600
    invoice = _reload(db_session, inv["id"])
    assert _amount(db_session, r2) == 600
    assert invoice.net == 120  # the urgent fee stays on the invoice
    assert _amount(db_session, r1) + _amount(db_session, r2) == 1000 < invoice.paid


def test_technician_never_sees_refund_amounts(client, db_session):
    inv = _create_invoice(client, db_session, [C], paid=150)
    line_id = _line_id(inv, C)
    assert client.get("/refunds", headers=TECH_KAMAL_HEADERS).status_code == 403
    assert client.get(f"/refunds/eligibility/{line_id}", headers=TECH_KAMAL_HEADERS).status_code == 403
    assert client.post(
        "/refunds", headers=TECH_KAMAL_HEADERS, json={"invoice_line_id": line_id, "reason": "x"}
    ).status_code == 403

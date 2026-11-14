"""
Prompt 13 - pre-lock line cancellation. Prompt 13A removed the approval step for this path (it now takes
effect at once); the Admin/Owner review code remains only for requests that were already pending.

One calculation (refund_service.compute_cancellation_outcome) feeds the preview, the approval view and
the invoice figures. Runs only against medscope_test (conftest guard).
Owner regression case: invoice 9000, advance paid 3000, cancel the 5000 line.
"""
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.models.audit import AuditLog
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.user import Staff
from backend.app.models.refund import RefundRequest
from backend.app.models.test import Test
from backend.app.services import refund_service
from tests.conftest import ADMIN_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS

TENANT = "center-seba-01"


def _test(db, price):
    code = f"P13_{uuid4().hex[:8].upper()}"
    db.add(Test(tenant_id=TENANT, code=code, name=f"13 probe {code}", department="Clinical Pathology", price=price,
                sample_type="Blood", performing_role="LAB_TECH", requires_doctor=False, report_template="NUMERIC_TABLE",
                approval_rule="TECHNICIAN_FINAL", is_outsourced=False, active=True, lab_section="HEMATOLOGY"))
    db.commit()
    return code


def _open_day(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st["is_open"]:
        assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201


def _owner_case(client, db, paid=3000):
    """9000 invoice = a 5000 line + a 4000 line, `paid` taka received up front."""
    _open_day(client)
    big, small = _test(db, 5000), _test(db, 4000)
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json={
        "patient_id": pid, "age_value": 30, "gender": "Male",
        "lines": [{"test_id": db.execute(select(Test.id).where(Test.code == c)).scalar_one()} for c in (big, small)],
        "initial_payment_amount": paid, "initial_payment_method": "CASH",
    })
    assert res.status_code == 201, res.text
    inv = res.json()
    line = next(l for l in inv["lines"] if l["test_code_snapshot"] == big)
    return inv, line["id"]


def _detail(client, inv_id):
    res = client.get(f"/invoices/{inv_id}", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    return res.json()


def _line(detail, line_id):
    return next(l for l in detail["lines"] if l["id"] == line_id)


def _request(client, inv, line_id, **extra):
    return client.post("/refunds/request", headers=RECEPTIONIST_HEADERS,
                       json={"invoice_id": inv["id"], "invoice_line_id": line_id, **extra})


def _sample_taken(client, db, line_id):
    db.expire_all()
    order = db.get(InvoiceLine, line_id).test_order
    res = client.post(f"/worklist/{order.id}/sample-taken", headers=ADMIN_HEADERS, json={})
    assert res.status_code == 200, res.text
    return order.id


def _legacy_pending(db, inv, line_id):
    """A request filed under the old Prompt 13 flow (still pending approval). The API no longer creates
    these; the Admin/Owner review code is kept so any already-pending request can still be resolved."""
    db.expire_all()
    line = db.get(InvoiceLine, line_id)
    req = RefundRequest(
        tenant_id=TENANT, invoice_id=inv["id"], invoice_line_id=line_id,
        amount=refund_service.compute_line_refundable_amount(line.invoice, line), reason="(legacy pending)",
        request_type="PRE_SAMPLE_CANCELLATION", status="PENDING_ADMIN_APPROVAL",
        requested_by_id=db.execute(select(Staff.id).where(Staff.username == "reception_fatima")).scalar_one(),
    )
    db.add(req)
    db.commit()
    return req.id


def test_receptionist_cancels_line_at_once_and_client_amount_is_ignored(client, db_session):
    inv, line_id = _owner_case(client, db_session)  # 9000, paid 3000, cancel the 5000 line
    res = _request(client, inv, line_id, amount=3000, request_type="D15_NOT_PERFORMED")  # both ignored
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["request_type"] == "PRE_SAMPLE_CANCELLATION"
    assert body["amount"] == 0 and body["status"] == "COMPLETED"  # server calculation; nothing to refund
    d = _detail(client, inv["id"])
    line = _line(d, line_id)
    assert line["status"] == "CANCELLED" and line["cancellation_state"] == "CANCELLED" and line["display_status"] == "CANCELLED"
    assert (d["net"], d["paid"], d["due"]) == (4000, 3000, 1000)


def test_owner_numbers_modal_equals_grid(client, db_session):
    """9000 / 3000 paid / 5000 line: retained 3000, refund 0, new due 1000 - identical in the preview
    (modal) and the invoice figures the grid shows right after the cancellation."""
    inv, line_id = _owner_case(client, db_session)
    pv = client.get(f"/refunds/preview/{line_id}", headers=RECEPTIONIST_HEADERS)
    assert pv.status_code == 200, pv.text
    p = pv.json()
    assert (p["invoice_total"], p["paid_total"], p["line_price"]) == (9000, 3000, 5000)
    assert (p["retained_amount"], p["refund_amount"], p["due_after"], p["net_after"]) == (3000, 0, 1000, 4000)
    assert p["can_request"] is True

    # the preview is the single calculation function's output, field for field
    db_session.expire_all()
    line = db_session.get(InvoiceLine, line_id)
    out = refund_service.compute_cancellation_outcome(line.invoice, line)
    keys = ("invoice_total", "paid_total", "line_price", "retained_amount", "refund_amount", "due_after", "net_after")
    for key in keys:
        assert p[key] == out[key]

    assert _request(client, inv, line_id, reason="patient declined").status_code == 201
    d = _detail(client, inv["id"])  # what the grid shows
    assert (d["net"], d["paid"], d["due"]) == (p["net_after"], 3000, p["due_after"])


def test_legacy_pending_approval_view_shows_live_figures_beside_the_snapshot(client, db_session):
    inv, line_id = _owner_case(client, db_session, paid=9000)
    req_id = _legacy_pending(db_session, inv, line_id)  # snapshot 5000
    db_session.expire_all()
    db_session.get(Invoice, inv["id"]).paid = 6000
    db_session.commit()
    bd = client.get(f"/refunds/requests/{req_id}/breakdown", headers=ADMIN_HEADERS).json()
    assert bd["snapshot_refund_amount"] == 5000 and bd["refund_amount"] == 2000 and bd["differs_from_snapshot"] is True
    ok = client.post(f"/refunds/review/{req_id}", headers=ADMIN_HEADERS, json={"action": "APPROVE", "review_notes": "ok"})
    assert ok.json()["amount"] == 2000  # binding amount is the live one


def test_request_on_locked_line_is_a_distinct_409(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    _sample_taken(client, db_session, line_id)
    res = _request(client, inv, line_id)
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "SAMPLE_ALREADY_TAKEN"
    pv = client.get(f"/refunds/preview/{line_id}", headers=RECEPTIONIST_HEADERS).json()
    assert pv["can_request"] is False and pv["blocker"] == "SAMPLE_ALREADY_TAKEN"
    assert _line(_detail(client, inv["id"]), line_id)["can_request_cancellation"] is False
    db_session.expire_all()
    assert db_session.execute(select(RefundRequest).where(RefundRequest.invoice_line_id == line_id)).first() is None
    assert db_session.get(InvoiceLine, line_id).status != "CANCELLED"


def test_rejected_specimen_is_refused_not_delegated_to_d15(client, db_session):
    """No third path: a spoiled/rejected specimen is refused here (409) instead of being silently
    turned into a D15 request by a front-desk user."""
    inv, line_id = _owner_case(client, db_session)
    order_id = _sample_taken(client, db_session, line_id)
    rej = client.post(f"/worklist/{order_id}/reject-sample", headers=ADMIN_HEADERS, json={"rejection_reason": "hemolysed"})
    assert rej.status_code == 200, rej.text
    res = _request(client, inv, line_id, request_type="D15_NOT_PERFORMED")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "SAMPLE_ALREADY_TAKEN"
    db_session.expire_all()
    assert db_session.execute(select(RefundRequest).where(RefundRequest.invoice_line_id == line_id)).first() is None


def test_second_cancellation_is_409_and_pending_legacy_request_blocks(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    assert _request(client, inv, line_id).status_code == 201
    again = _request(client, inv, line_id)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_CANCELLED"
    assert _line(_detail(client, inv["id"]), line_id)["can_request_cancellation"] is False

    inv2, line2 = _owner_case(client, db_session)
    _legacy_pending(db_session, inv2, line2)
    blocked = _request(client, inv2, line2)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "REQUEST_PENDING"


def test_legacy_pending_approval_needs_admin_and_a_reason(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    req_id = _legacy_pending(db_session, inv, line_id)
    url = f"/refunds/review/{req_id}"
    assert client.post(url, headers=RECEPTIONIST_HEADERS, json={"action": "APPROVE", "review_notes": "x"}).status_code == 403
    assert client.post(url, headers=ADMIN_HEADERS, json={"action": "APPROVE"}).status_code == 400
    assert client.post(url, headers=ADMIN_HEADERS, json={"action": "APPROVE", "review_notes": "  "}).status_code == 400
    assert client.post(url, headers=OWNER_HEADERS, json={"action": "APPROVE", "review_notes": "ok"}).status_code == 200


def test_legacy_pending_approval_after_sample_taken_is_refused(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    req_id = _legacy_pending(db_session, inv, line_id)
    _sample_taken(client, db_session, line_id)
    res = client.post(f"/refunds/review/{req_id}", headers=ADMIN_HEADERS, json={"action": "APPROVE", "review_notes": "ok"})
    assert res.status_code == 409 and res.json()["detail"]["code"] == "SAMPLE_ALREADY_TAKEN"
    db_session.expire_all()
    assert db_session.get(InvoiceLine, line_id).status != "CANCELLED"


def test_status_precedence_and_full_lifecycle_under_one_invoice(client, db_session):
    inv, line_id = _owner_case(client, db_session, paid=9000)
    d0 = _line(_detail(client, inv["id"]), line_id)
    assert d0["cancellation_state"] == "NONE" and d0["display_status"] == "Awaiting collection"

    res = _request(client, inv, line_id, reason="left")
    assert res.status_code == 201, res.text
    req_id = res.json()["id"]
    assert res.json()["status"] == "APPROVED"  # no approval step; refund awaits payout
    d2 = _detail(client, inv["id"])
    l2 = _line(d2, line_id)
    # the stale sample label does not win over the cancellation state
    assert l2["status"] == "CANCELLED" and l2["cancellation_state"] == "CANCELLED_REFUND_PENDING"
    assert l2["display_status"] == "CANCELLED - REFUND PENDING PAYOUT" and l2["can_request_cancellation"] is False
    assert (d2["net"], d2["paid"], d2["due"]) == (4000, 9000, 0) and d2["refund_due"] == 5000

    assert client.post(f"/refunds/disburse/{req_id}", headers=RECEPTIONIST_HEADERS, json={"method": "CASH"}).status_code == 200
    d3 = _detail(client, inv["id"])
    assert _line(d3, line_id)["display_status"] == "CANCELLED - REFUNDED"
    assert d3["refund_due"] == 0 and d3["refund_status"] == "PARTIALLY_REFUNDED"

    # everything is reachable from the one invoice id
    assert [r["id"] for r in d3["refund_requests"]] == [req_id]
    r = d3["refund_requests"][0]
    assert r["status"] == "DISBURSED" and r["reviewed_by_id"] is None and r["disbursed_by_id"]
    db_session.expire_all()
    actions = {a.action for a in db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "REFUND_REQUEST", AuditLog.entity_id == str(req_id))).scalars()}
    assert {"PRE_LOCK_CANCELLATION", "REFUND_DISBURSED"} <= actions
    assert "ADMIN_REVIEW_REFUND_APPROVED" not in actions


def test_legacy_rejected_request_leaves_line_normal_and_cancellable(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    first = _legacy_pending(db_session, inv, line_id)
    assert client.post(f"/refunds/review/{first}", headers=ADMIN_HEADERS, json={"action": "REJECT", "review_notes": "no"}).status_code == 200
    d = _line(_detail(client, inv["id"]), line_id)
    assert d["cancellation_state"] == "NONE" and d["can_request_cancellation"] is True
    assert _request(client, inv, line_id).status_code == 201
    assert _line(_detail(client, inv["id"]), line_id)["cancellation_state"] == "CANCELLED"


def test_cancellation_is_atomic(client, db_session, monkeypatch):
    inv, line_id = _owner_case(client, db_session)

    def boom(*a, **k):
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr(refund_service, "log_audit_event", boom)
    with pytest.raises(RuntimeError):
        _request(client, inv, line_id)
    monkeypatch.undo()
    db_session.expire_all()
    assert db_session.execute(select(RefundRequest).where(RefundRequest.invoice_line_id == line_id)).first() is None
    assert db_session.get(InvoiceLine, line_id).status != "CANCELLED"
    inv_row = db_session.get(Invoice, inv["id"])
    assert inv_row.refund_status == "NO_REFUND" and inv_row.net == 9000
    assert _request(client, inv, line_id).status_code == 201  # and the line is still cancellable

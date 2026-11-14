"""
Prompt 13A - pre-lock cancellation without an approval step, plus the explicit whole-invoice action.

- Receptionist, Cashier, Admin and Owner can each cancel a line at once (no Admin/Owner sign-off).
- Whole invoice: every line together, only when no line is locked (409 otherwise, nothing changes).
  Same single calculation (compute_cancellation_outcome) line by line; the confirmation view is the sum.
- Prompt 13B: cancelling never pays out; disbursement is a separate call.
- D15 (post-lock, Not Performed) still needs Admin/Owner approval; its request does not cancel anything.
Runs only against medscope_test (conftest guard).
"""
import pytest
from sqlalchemy import select

from backend.app.models.audit import AuditLog
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.refund import RefundRequest
from backend.app.services import refund_service
from tests.conftest import (
    ADMIN_HEADERS, CASHIER_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS,
)
from tests.test_prompt13_prelock_cancellation import _detail, _line, _owner_case, _request, _sample_taken


def _whole(client, inv_id, headers=RECEPTIONIST_HEADERS, **body):
    return client.post("/refunds/cancel-invoice", headers=headers, json={"invoice_id": inv_id, **body})


@pytest.mark.parametrize("headers", [RECEPTIONIST_HEADERS, CASHIER_HEADERS, ADMIN_HEADERS, OWNER_HEADERS])
def test_every_front_desk_role_cancels_a_line_without_approval(client, db_session, headers):
    inv, line_id = _owner_case(client, db_session, paid=9000)
    res = client.post("/refunds/request", headers=headers, json={"invoice_id": inv["id"], "invoice_line_id": line_id})
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "APPROVED" and res.json()["amount"] == 5000  # effective now, payout pending
    assert _line(_detail(client, inv["id"]), line_id)["status"] == "CANCELLED"


def test_lab_tech_cannot_cancel_a_line_or_an_invoice(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    assert client.post("/refunds/request", headers=TECH_KAMAL_HEADERS, json={"invoice_id": inv["id"], "invoice_line_id": line_id}).status_code == 403
    assert _whole(client, inv["id"], TECH_KAMAL_HEADERS).status_code == 403
    assert client.get(f"/refunds/preview-invoice/{inv['id']}", headers=TECH_KAMAL_HEADERS).status_code == 403
    assert _line(_detail(client, inv["id"]), line_id)["status"] != "CANCELLED"


def test_whole_invoice_preview_is_the_sum_of_the_single_function(client, db_session):
    inv, line_id = _owner_case(client, db_session)  # 5000 + 4000, paid 3000
    p = client.get(f"/refunds/preview-invoice/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert p["can_cancel"] is True and (p["invoice_total"], p["paid_total"]) == (9000, 3000)
    # line 1 (5000): net_after 4000 -> refund 0; line 2 (4000, sees line 1): net_after 0 -> refund 3000
    assert [r["refund_amount"] for r in p["lines"]] == [0, 3000] or sorted(r["refund_amount"] for r in p["lines"]) == [0, 3000]
    assert (p["total_refund"], p["retained_amount"], p["due_after"], p["net_after"]) == (3000, 0, 0, 0)

    # independent re-derivation with compute_cancellation_outcome on the real invoice, no mutation
    db_session.expire_all()
    inv_row = db_session.get(Invoice, inv["id"])
    lines = sorted(inv_row.lines, key=lambda l: l.id)
    sim = refund_service._SimInvoice(inv_row)
    total = 0
    for l in lines:
        out = refund_service.compute_cancellation_outcome(sim, l)
        total += out["refund_amount"]
        sim.net = out["net_after"]
        sim.refund_requests.append(refund_service._SimRequest(out["refund_amount"]))
    assert total == p["total_refund"]
    assert db_session.get(Invoice, inv["id"]).net == 9000  # preview changed nothing


def test_whole_invoice_cancels_every_line_together_then_disburse_is_a_separate_step(client, db_session):
    inv, _ = _owner_case(client, db_session)
    p = client.get(f"/refunds/preview-invoice/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    res = _whole(client, inv["id"], reason="family emergency")
    assert res.status_code == 201, res.text
    rows = res.json()
    assert len(rows) == 2 and sum(r["amount"] for r in rows) == p["total_refund"] == 3000
    assert {r["status"] for r in rows} == {"APPROVED", "COMPLETED"}  # nothing paid out by the cancel
    d = _detail(client, inv["id"])
    assert all(l["status"] == "CANCELLED" for l in d["lines"])
    assert (d["net"], d["due"], d["refund_due"]) == (0, 0, 3000)  # refund due until disbursed
    db_session.expire_all()
    assert not db_session.execute(select(RefundRequest).where(
        RefundRequest.invoice_id == inv["id"], RefundRequest.status.in_(("PENDING_ADMIN_APPROVAL", "DISBURSED")))).first()
    actions = {a.action for a in db_session.execute(select(AuditLog).where(AuditLog.entity_id == str(inv["id"]))).scalars()}
    assert "PRE_LOCK_INVOICE_CANCELLATION" in actions

    payable = next(r for r in rows if r["status"] == "APPROVED")
    dis = client.post(f"/refunds/disburse/{payable['id']}", headers=RECEPTIONIST_HEADERS, json={"method": "CASH"})
    assert dis.status_code == 200 and dis.json()["status"] == "DISBURSED"
    assert _detail(client, inv["id"])["refund_due"] == 0
    again = _whole(client, inv["id"])
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALREADY_CANCELLED"


def test_whole_invoice_without_channel_leaves_refund_awaiting_payout(client, db_session):
    inv, _ = _owner_case(client, db_session, paid=9000)
    res = _whole(client, inv["id"])
    assert res.status_code == 201, res.text
    assert sum(r["amount"] for r in res.json()) == 9000
    d = _detail(client, inv["id"])
    assert d["refund_due"] == 9000 and d["refund_status"] == "REFUND_APPROVED"


def test_whole_invoice_is_blocked_when_any_line_is_locked_and_nothing_changes(client, db_session):
    inv, line_id = _owner_case(client, db_session)
    _sample_taken(client, db_session, line_id)  # one line locked
    pv = client.get(f"/refunds/preview-invoice/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert pv["can_cancel"] is False and pv["blocker"] == "SAMPLE_ALREADY_TAKEN"
    res = _whole(client, inv["id"])
    assert res.status_code == 409 and res.json()["detail"]["code"] == "SAMPLE_ALREADY_TAKEN"
    d = _detail(client, inv["id"])
    assert all(l["status"] != "CANCELLED" for l in d["lines"]) and d["net"] == 9000
    db_session.expire_all()
    assert db_session.execute(select(RefundRequest).where(RefundRequest.invoice_id == inv["id"])).first() is None
    # the untouched line can still be cancelled on its own
    other = next(l for l in d["lines"] if l["id"] != line_id)
    assert _request(client, inv, other["id"]).status_code == 201


def test_cancelling_can_never_pay_out_even_if_a_channel_is_sent(client, db_session):
    """Prompt 13B: a disbursement_method / reference in a cancel body is ignored; nothing is paid out."""
    inv, line_id = _owner_case(client, db_session, paid=9000)
    res = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json={
        "invoice_id": inv["id"], "invoice_line_id": line_id, "disbursement_method": "CASH", "disbursement_reference": "X1"})
    assert res.status_code == 201 and res.json()["status"] == "APPROVED"
    assert res.json()["disbursed_at"] is None and res.json()["disbursement_method"] is None

    inv2, _ = _owner_case(client, db_session, paid=9000)
    rows = _whole(client, inv2["id"], disbursement_method="CASH", disbursement_reference="X2").json()
    assert all(r["status"] != "DISBURSED" and r["disbursed_at"] is None for r in rows)
    assert _detail(client, inv2["id"])["refund_due"] == 9000

    from backend.app.schemas.refund import RefundRequestCreate, InvoiceCancellationCreate
    assert "disbursement_method" not in RefundRequestCreate.model_fields
    assert "disbursement_method" not in InvoiceCancellationCreate.model_fields


def test_whole_invoice_is_atomic_when_a_later_step_fails(client, db_session, monkeypatch):
    inv, _ = _owner_case(client, db_session)
    calls = {"n": 0}
    real = refund_service.log_audit_event

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:  # the second line's audit row fails after the first line was already cancelled
            raise RuntimeError("forced failure")
        return real(*a, **k)

    monkeypatch.setattr(refund_service, "log_audit_event", flaky)
    with pytest.raises(RuntimeError):
        _whole(client, inv["id"])
    monkeypatch.undo()
    db_session.expire_all()
    inv_row = db_session.get(Invoice, inv["id"])
    assert inv_row.net == 9000 and all(l.status != "CANCELLED" for l in inv_row.lines)
    assert db_session.execute(select(RefundRequest).where(RefundRequest.invoice_id == inv["id"])).first() is None


def test_d15_post_lock_path_still_needs_approval(client, db_session):
    inv, line_id = _owner_case(client, db_session, paid=9000)
    order_id = _sample_taken(client, db_session, line_id)
    assert client.post(f"/worklist/{order_id}/reject-sample", headers=ADMIN_HEADERS, json={"rejection_reason": "hemolysed"}).status_code == 200
    res = client.post(f"/worklist/{order_id}/d15-refund-request", headers=TECH_KAMAL_HEADERS)
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "PENDING_ADMIN_APPROVAL"
    db_session.expire_all()
    assert db_session.get(InvoiceLine, line_id).status != "CANCELLED"  # nothing cancelled until approval
    req_id = res.json()["id"]
    assert client.post(f"/refunds/review/{req_id}", headers=RECEPTIONIST_HEADERS, json={"action": "APPROVE"}).status_code == 403
    ok = client.post(f"/refunds/review/{req_id}", headers=ADMIN_HEADERS, json={"action": "APPROVE", "review_notes": "ok"})
    assert ok.status_code == 200, ok.text
    db_session.expire_all()
    assert db_session.get(InvoiceLine, line_id).status == "CANCELLED"

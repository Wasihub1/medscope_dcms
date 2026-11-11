"""
Prompt 07C Automated Test Suite: Safety and Correctness Fixes
Validates:
- Fix 1: D15 refund must go through original payment channel (and respect channel paid balance)
- Fix 2: Segregation of duties on refund approval (blocks self-approval with 403)
- Fix 3: Culture stage FINAL does not auto-complete TestOrder; completion requires FINAL stage
- Fix 4: Result-save guards (saving draft does not advance status, sample collection required for sample tests, completed orders immutable)
- Fix 5: Technician financial isolation (D15 refund response and event timeline amount-free for LAB_TECH)
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.payment import Payment
from backend.app.models.refund import RefundRequest
from backend.app.models.test_order import TestOrder, TestOrderEvent
from backend.app.models.sample import Sample
from backend.app.models.test import Test, TestComponent
from backend.app.models.user import Staff
from backend.app.core.timezone import utc_now
from tests.conftest import RECEPTIONIST_HEADERS, ADMIN_HEADERS, TECH_KAMAL_HEADERS


def test_fix1_original_payment_channel_enforcement(client, db_session):
    """Fix 1: Disbursing refund must use original payment channel and validate reference for non-cash."""
    # Find an approved refund request
    req = db_session.query(RefundRequest).filter(
        RefundRequest.tenant_id == "center-seba-01",
        RefundRequest.status == "APPROVED",
    ).first()

    if not req:
        # Create a mock approved refund request for testing
        inv = db_session.query(Invoice).filter(Invoice.tenant_id == "center-seba-01").first()
        line = inv.lines[0]
        # Ensure there is a payment recorded for this invoice in CASH
        pmt = db_session.query(Payment).filter(Payment.invoice_id == inv.id).first()
        if not pmt:
            pmt = Payment(
                tenant_id="center-seba-01",
                invoice_id=inv.id,
                amount=1000,
                method="CASH",
                received_by_id=1,
            )
            db_session.add(pmt)
            db_session.commit()

        req = RefundRequest(
            tenant_id="center-seba-01",
            invoice_id=inv.id,
            invoice_line_id=line.id,
            amount=line.net_price,
            reason="Test Fix 1 Original Channel",
            request_type="D15_NOT_PERFORMED",
            status="APPROVED",
            requested_by_id=3,
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)

    # Attempt to disburse using a channel that was NOT used on invoice payments (e.g. POS_CARD or BANK_TRANSFER)
    paid_methods = {p.method.upper() for p in req.invoice.payments}
    unpaid_method = "POS_CARD" if "POS_CARD" not in paid_methods else "BANK_TRANSFER"

    bad_res = client.post(
        f"/refunds/disburse/{req.id}",
        headers=RECEPTIONIST_HEADERS,
        json={"method": unpaid_method, "reference": "TRX-12345"},
    )
    assert bad_res.status_code == 400
    assert "Invalid disbursement channel" in bad_res.json()["detail"]

    # Attempt non-cash without reference (if BKASH is paid or test with missing reference)
    if "BKASH" in paid_methods:
        no_ref_res = client.post(
            f"/refunds/disburse/{req.id}",
            headers=RECEPTIONIST_HEADERS,
            json={"method": "BKASH", "reference": ""},
        )
        assert no_ref_res.status_code == 400
        assert "transaction reference ID is required" in no_ref_res.json()["detail"]


def test_fix2_segregation_of_duties_self_approval_blocked(client, db_session):
    """Fix 2: Admin cannot approve or review a refund request they submitted themselves."""
    inv = db_session.query(Invoice).filter(Invoice.tenant_id == "center-seba-01").first()
    line = inv.lines[0]

    # Admin (ID 2) submits a refund request
    req = RefundRequest(
        tenant_id="center-seba-01",
        invoice_id=inv.id,
        invoice_line_id=line.id,
        amount=500,
        reason="Admin Self-Approval Test Request",
        request_type="PRE_SAMPLE_CANCELLATION",
        status="PENDING_ADMIN_APPROVAL",
        requested_by_id=2,  # Admin Tariqul
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    # Admin Tariqul (ID 2) attempts to approve their own request -> 403 Forbidden
    res = client.post(
        f"/refunds/review/{req.id}",
        headers=ADMIN_HEADERS,  # ID 2
        json={"action": "APPROVE", "review_notes": "Trying to approve my own request"},
    )
    assert res.status_code == 403
    assert "Segregation of duties violation" in res.json()["detail"]


def _create_isolated_order(client, db_session, test_id=1, sample_status="COLLECTED"):
    inv_res = client.post(
        "/invoices",
        headers=RECEPTIONIST_HEADERS,
        json={
            "patient_id": 1,
            "lines": [{"test_id": test_id, "discount_type": "NONE", "discount_value": 0}],
            "initial_payment": 400,
            "payment_method": "CASH",
        },
    )
    assert inv_res.status_code in (200, 201), inv_res.text
    inv_id = inv_res.json()["id"]
    db_session.expire_all()
    inv_obj = db_session.query(Invoice).filter(Invoice.id == inv_id).first()
    line = inv_obj.lines[0]
    order = line.test_order
    order.assigned_to_id = 3  # Kamal Hossain
    order.status = "IN_PROGRESS"
    if sample_status:
        if not order.sample:
            smp = Sample(
                tenant_id="center-seba-01",
                test_order_id=order.id,
                sample_code=f"SMP-ISO-{order.id}",
                status=sample_status,
                collected_at=utc_now(),
            )
            db_session.add(smp)
        else:
            order.sample.status = sample_status
    db_session.commit()
    db_session.refresh(order)
    return order


def test_fix3_culture_stage_final_does_not_autocomplete(client, db_session):
    """Fix 3: Moving culture stage to FINAL leaves order IN_PROGRESS; cannot complete before FINAL."""
    order = _create_isolated_order(client, db_session, test_id=1, sample_status="COLLECTED")
    order.culture_stage = "INCUBATING"
    order.status = "IN_PROGRESS"
    db_session.commit()

    # 1. Attempting to complete culture test while in INCUBATING stage must be rejected
    fail_comp = client.post(
        f"/worklist/{order.id}/status",
        headers=TECH_KAMAL_HEADERS,
        json={"status": "COMPLETED", "notes": "Premature completion attempt"},
    )
    assert fail_comp.status_code == 400
    assert "must reach FINAL before completion" in fail_comp.json()["detail"]

    # 2. Progress stage to FINAL -> Must stay IN_PROGRESS (not auto-completed)
    final_res = client.post(
        f"/worklist/{order.id}/culture-stage",
        headers=TECH_KAMAL_HEADERS,
        json={"stage": "FINAL", "notes": "No growth detected after 72 hrs"},
    )
    assert final_res.status_code == 200
    db_session.refresh(order)
    assert order.culture_stage == "FINAL"
    assert order.status == "IN_PROGRESS"  # Decoupled!


def test_fix4_draft_does_not_advance_status(client, db_session):
    """Fix 4(b): Saving a draft does not advance order status from IN_PROGRESS."""
    order = _create_isolated_order(client, db_session, test_id=1, sample_status="COLLECTED")
    order.status = "IN_PROGRESS"
    db_session.commit()

    res = client.post(
        f"/worklist/{order.id}/result",
        headers=TECH_KAMAL_HEADERS,
        json={
            "status": "DRAFT",
            "findings": "Draft preliminary notes",
            "items": [],
        },
    )
    assert res.status_code == 200
    db_session.refresh(order)
    assert order.status == "IN_PROGRESS"  # Status NOT advanced!


def test_fix4_sample_uncollected_result_save_rejected(client, db_session):
    """Fix 4(c): Saving results on a sample-based test before specimen collection is rejected with HTTP 409."""
    order = _create_isolated_order(client, db_session, test_id=1, sample_status=None)
    order.status = "SAMPLE_PENDING"
    if order.sample:
        order.sample.status = "PENDING"
    db_session.commit()

    res = client.post(
        f"/worklist/{order.id}/result",
        headers=TECH_KAMAL_HEADERS,
        json={
            "status": "DRAFT",
            "findings": "Attempting result entry before specimen collection",
            "items": [],
        },
    )
    assert res.status_code == 409
    assert "specimen has not been collected" in res.json()["detail"].lower()


def test_fix4_completed_order_resave_rejected(client, db_session):
    """Fix 4(a): Modifying results on an already COMPLETED order is rejected with HTTP 409."""
    order = _create_isolated_order(client, db_session, test_id=1, sample_status="COLLECTED")
    order.status = "COMPLETED"
    db_session.commit()

    res = client.post(
        f"/worklist/{order.id}/result",
        headers=TECH_KAMAL_HEADERS,
        json={
            "status": "DRAFT",
            "findings": "Attempting to overwrite completed order",
            "items": [],
        },
    )
    assert res.status_code == 409
    assert "completed test order" in res.json()["detail"].lower()


def test_fix5_technician_financial_isolation(client, db_session):
    """Fix 5: D15 refund endpoint returns clinical response (no amount) and event timeline sanitizes amounts."""
    order = _create_isolated_order(client, db_session, test_id=1, sample_status="REJECTED")
    order.status = "REJECTED"
    if order.sample:
        order.sample.rejection_reason = "Hemolyzed specimen"
    db_session.commit()

    # 1. Test D15 refund request response schema
    res = client.post(
        f"/worklist/{order.id}/d15-refund-request?notes=Fix5Verification",
        headers=TECH_KAMAL_HEADERS,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert "amount" not in data, "Financial leak: amount present in technician D15 response"
    assert "price" not in data
    assert "test_order_id" in data
    assert data["message"] == "D15 refund request submitted for Admin/Owner approval."

    # 2. Test event timeline sanitization for LAB_TECH
    ev_res = client.get(
        f"/worklist/{order.id}/events",
        headers=TECH_KAMAL_HEADERS,
    )
    assert ev_res.status_code == 200
    events = ev_res.json()
    for ev in events:
        desc = ev.get("description", "")
        assert "Tk " not in desc, f"Financial leak in event description: {desc}"
        assert "৳" not in desc, f"Financial leak in event description: {desc}"

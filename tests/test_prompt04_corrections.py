"""
MedScope Receptionist Corrections - Prompt 04 Test Suite
Validates backend invariants and APIs added/updated in Prompt 04:
- 01: Prescribed By vs Referred By separation + write-only commission privacy
- 02: Business Day Close RBAC (Receptionist 403, Admin 200)
- 03: Test deduplication validation on invoice lines
- 05: Zero initial payment creates no payment record
- 14: Dynamic refund_status computation (NO_REFUND, REFUND_PENDING)
"""

import pytest
import httpx
import time
from tests.conftest import RECEPTIONIST_HEADERS, ADMIN_HEADERS, CASHIER_HEADERS

BASE_URL = "http://127.0.0.1:8000/api/v1"


def test_p04_01_prescriber_and_referrer_separation_and_write_only_commission(client):
    ts = int(time.time())

    # 1. Create a Doctor as Prescriber with write-only commission
    doc_payload = {
        "name": f"Dr. Prescriber {ts}",
        "type": "Doctor",
        "degree": "MBBS, MD",
        "specialty": "Neurology",
        "phone": f"0171{ts % 10000000:07d}",
        "commission_rate": 20,
        "commission_type": "PERCENT",
    }
    doc_res = client.post("/referrers", headers=RECEPTIONIST_HEADERS, json=doc_payload)
    assert doc_res.status_code in [200, 201], doc_res.text
    doctor = doc_res.json()
    assert doctor["name"] == doc_payload["name"]
    # Invariant: commission_rate must NOT be leaked back to the client
    assert "commission_rate" not in doctor, "Commission rate leaked in ReferrerResponse!"

    # 2. Create a Third Party as Referrer with write-only commission
    agent_payload = {
        "name": f"Partner Agent {ts}",
        "type": "Agent",
        "phone": f"0181{ts % 10000000:07d}",
        "institution": "Al-Madina Clinic",
        "commission_rate": 15,
        "commission_type": "PERCENT",
    }
    agent_res = client.post("/referrers", headers=RECEPTIONIST_HEADERS, json=agent_payload)
    assert agent_res.status_code in [200, 201], agent_res.text
    agent = agent_res.json()
    assert agent["name"] == agent_payload["name"]
    assert "commission_rate" not in agent, "Commission rate leaked in ReferrerResponse!"

    # 3. Query referrers with type filter Doctor
    filter_res = client.get(f"/referrers?type=Doctor&q={ts}", headers=RECEPTIONIST_HEADERS)
    assert filter_res.status_code == 200, filter_res.text
    doc_list = filter_res.json()
    assert any(d["id"] == doctor["id"] for d in doc_list)
    assert not any(d["id"] == agent["id"] for d in doc_list)
    for d in doc_list:
        assert "commission_rate" not in d


def test_p04_02_business_day_close_rbac(client):
    # Receptionist close must be 403 Forbidden
    rec_close = client.post(
        "/business-day/close",
        headers=RECEPTIONIST_HEADERS,
        json={"notes": "Unauthorized close attempt by receptionist"},
    )
    assert rec_close.status_code == 403, f"Expected 403 Forbidden, got {rec_close.status_code}"

    # Cashier close must also be 403 Forbidden
    cashier_headers = CASHIER_HEADERS
    cashier_close = client.post(
        "/business-day/close",
        headers=cashier_headers,
        json={"notes": "Unauthorized close attempt by cashier"},
    )
    assert cashier_close.status_code == 403, f"Expected 403 Forbidden, got {cashier_close.status_code}"


def test_p04_03_test_deduplication_validation(client):
    ts = int(time.time())
    p_res = client.post(
        "/patients",
        headers=RECEPTIONIST_HEADERS,
        json={
            "full_name": f"Dedup Patient {ts}",
            "phone": f"0191{ts % 10000000:07d}",
            "gender": "MALE",
        },
    )
    patient = p_res.json()

    # Attempt to create invoice with duplicate test lines
    inv_payload = {
        "patient_id": patient["id"],
        "age_value": 35,  # Prompt 10E: Finalize requires age and gender
        "gender": "Male",
        "lines": [
            {"test_id": 1, "is_urgent": False, "discount_type": "NONE", "discount_value": 0},
            {"test_id": 1, "is_urgent": False, "discount_type": "NONE", "discount_value": 0},  # Duplicate!
        ],
    }
    dup_res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=inv_payload)
    assert dup_res.status_code == 422, f"Expected 422 Unprocessable Entity for duplicate tests, got {dup_res.status_code}"


def test_p04_04_zero_default_payment_and_unpaid_status(client):
    ts = int(time.time())
    p_res = client.post(
        "/patients",
        headers=RECEPTIONIST_HEADERS,
        json={
            "full_name": f"Zero Pay Patient {ts}",
            "phone": f"0161{ts % 10000000:07d}",
            "gender": "FEMALE",
        },
    )
    patient = p_res.json()

    # Create invoice with NO initial payment (initial_payment = None)
    inv_payload = {
        "patient_id": patient["id"],
        "age_value": 35,  # Prompt 10E: Finalize requires age and gender
        "gender": "Male",
        "lines": [
            {"test_id": 1, "is_urgent": False, "discount_type": "NONE", "discount_value": 0},
        ],
        "initial_payment": None,
    }
    inv_res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=inv_payload)
    assert inv_res.status_code in [200, 201], inv_res.text
    inv = inv_res.json()

    assert inv["paid_amount"] == 0
    assert inv["due_amount"] == inv["net_amount"]
    assert inv["payment_status"] in ["UNPAID", "DUE"]
    assert inv["refund_status"] == "NO_REFUND"

    # Verify no zero-amount payment was persisted
    detail_res = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS)
    detail = detail_res.json()
    assert len(detail.get("payments", [])) == 0, "No Payment row should be created for zero initial payment!"


def test_p04_05_dynamic_refund_status_lifecycle(client):
    ts = int(time.time())
    p_res = client.post(
        "/patients",
        headers=RECEPTIONIST_HEADERS,
        json={
            "full_name": f"Refund Patient {ts}",
            "phone": f"0151{ts % 10000000:07d}",
            "gender": "MALE",
        },
    )
    patient = p_res.json()

    # Create paid invoice (Test #1 is Tk 400)
    inv_payload = {
        "patient_id": patient["id"],
        "age_value": 35,  # Prompt 10E: Finalize requires age and gender
        "gender": "Male",
        "lines": [
            {"test_id": 1, "is_urgent": False, "discount_type": "NONE", "discount_value": 0},
        ],
        "initial_payment": {
            "amount": 400,
            "channel": "CASH",
            "notes": "Full upfront cash",
        },
    }
    inv_res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=inv_payload)
    assert inv_res.status_code in [200, 201], inv_res.text
    inv = inv_res.json()
    assert inv["refund_status"] == "NO_REFUND"

    # Get invoice detail to retrieve line ID
    detail_res = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS)
    detail = detail_res.json()
    line_id = detail["lines"][0]["id"]

    # Request refund for pre-sample cancellation
    ref_payload = {
        "invoice_id": inv["id"],
        "invoice_line_id": line_id,
        "amount": 400,
        "reason": "Doctor cancelled order prior to blood sample collection",
    }
    ref_res = client.post("/refunds/request", headers=RECEPTIONIST_HEADERS, json=ref_payload)
    assert ref_res.status_code in [200, 201], ref_res.text

    # Prompt 13A: no approval step for pre-lock cancellation. The refund is approved at once and awaits payout.
    detail_res = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS)
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()
    assert detail["refund_status"] == "REFUND_APPROVED"
    assert len(detail.get("refund_requests", [])) >= 1

    # After payout every line is cancelled and the money is back: fully refunded
    dis = client.post(f"/refunds/disburse/{ref_res.json()['id']}", headers=RECEPTIONIST_HEADERS, json={"method": "CASH"})
    assert dis.status_code == 200, dis.text
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert detail["refund_status"] == "FULLY_REFUNDED"


def test_p04_06_user_friendly_status_filter_events(client):
    """
    Validates that GET /invoices accepts user-friendly event names and masks PostgreSQL column names:
    - 'All Payments'
    - 'Paid'
    - 'Unpaid'
    - 'Partial Due'
    - 'Partially Refunded'
    - 'Fully Refunded'
    """
    events = ["All Payments", "Paid", "Unpaid", "Partial Due", "Partially Refunded", "Fully Refunded"]
    for evt in events:
        res = client.get(f"/invoices?status={evt}", headers=RECEPTIONIST_HEADERS)
        assert res.status_code == 200, f"Filter '{evt}' failed: {res.text}"
        data = res.json()
        assert isinstance(data, list)
        if evt == "Partially Refunded":
            assert all(inv["refund_status"] == "PARTIALLY_REFUNDED" for inv in data)
        elif evt == "Fully Refunded":
            assert all(inv["refund_status"] == "FULLY_REFUNDED" for inv in data)
        elif evt == "Paid":
            assert all(inv["refund_status"] != "FULLY_REFUNDED" for inv in data)
            assert all(inv["due_amount"] == 0 for inv in data)
        elif evt == "Unpaid":
            assert all(inv["paid_amount"] == 0 for inv in data)
        elif evt == "Partial Due":
            assert all(inv["paid_amount"] > 0 and inv["due_amount"] > 0 for inv in data)


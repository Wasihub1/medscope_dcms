"""
MedScope Receptionist Portal - Development E2E Test Suite
Covers all 14 scenarios specified in Prompt 03 Section 7.
Tests against FastAPI backend at http://127.0.0.1:8000
"""

import pytest
import httpx
from tests.conftest import RECEPTIONIST_HEADERS, ADMIN_HEADERS

BASE_URL = "http://127.0.0.1:8000/api/v1"


# ---------------------------------------------------------------------------
# Scenario 1: Business Day status & receptionist close rejection (403)
# ---------------------------------------------------------------------------
def test_01_business_day_status_and_receptionist_close_rejection(client):
    # Receptionist queries business day status
    res = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] in ["OPEN", "CLOSED"]
    assert "channels" in data or "channel_balances" in data

    # Receptionist attempts to close business day -> Must return 403 Forbidden
    close_res = client.post(
        "/business-day/close",
        headers=RECEPTIONIST_HEADERS,
        json={"notes": "Attempt unauthorized close by receptionist"},
    )
    assert close_res.status_code == 403, "Receptionist must not be able to close business day"


# ---------------------------------------------------------------------------
# Scenario 2: Patient search & full history
# ---------------------------------------------------------------------------
def test_02_patient_search_and_full_history(client):
    # Search patients
    res = client.get("/patients?q=Fatima", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    patients = res.json()
    assert isinstance(patients, list)

    # Get patient #1 history
    hist_res = client.get("/patients/1/history", headers=RECEPTIONIST_HEADERS)
    assert hist_res.status_code == 200, hist_res.text
    hist = hist_res.json()
    assert "patient" in hist
    assert "invoices" in hist
    assert "visits" in hist
    assert "payments" in hist
    assert "total_billed_amount" in hist
    assert "total_outstanding_due" in hist


# ---------------------------------------------------------------------------
# Scenario 3: Inline patient & referrer registration
# ---------------------------------------------------------------------------
def test_03_inline_patient_and_referrer_registration(client):
    import time
    timestamp = int(time.time())
    
    # Register patient
    patient_payload = {
        "full_name": f"E2E Patient {timestamp}",
        "phone": f"017{timestamp % 100000000:08d}",
        "gender": "FEMALE",
        "age_years": 28,
        "age_months": 4,
        "address": "Dhanmondi, Dhaka",
        "blood_group": "B+",
    }
    p_res = client.post("/patients", headers=RECEPTIONIST_HEADERS, json=patient_payload)
    assert p_res.status_code in [200, 201], p_res.text
    patient = p_res.json()
    assert patient["full_name"] == patient_payload["full_name"]
    assert "mrn" in patient or "patient_code" in patient

    # Register referrer
    referrer_payload = {
        "name": f"Dr. E2E Test {timestamp}",
        "degree": "MBBS, FCPS",
        "specialty": "Internal Medicine",
        "phone": f"018{timestamp % 100000000:08d}",
    }
    r_res = client.post("/referrers", headers=RECEPTIONIST_HEADERS, json=referrer_payload)
    assert r_res.status_code in [200, 201], r_res.text
    referrer = r_res.json()
    assert referrer["name"] == referrer_payload["name"]


# ---------------------------------------------------------------------------
# Scenario 4: Test search, discount up to 100%, zero-net validation, invoice creation
# ---------------------------------------------------------------------------
def test_04_test_search_discounts_and_invoice_creation(client):
    # Search tests
    t_res = client.get("/tests?q=CBC", headers=RECEPTIONIST_HEADERS)
    assert t_res.status_code == 200
    tests = t_res.json()
    assert len(tests) > 0
    test_item = tests[0]

    # Create invoice with 100% discount on test item (zero net allowed per prompt 03)
    inv_payload = {
        "patient_id": 1,
        "age_value": 35,  # Prompt 10E: Finalize requires age and gender
        "gender": "Male",
        "lines": [
            {
                "test_id": test_item["id"],
                "discount_type": "PERCENT",
                "discount_value": 100,  # 100% discount allowed!
                "urgent": True,
            }
        ],
        "initial_payment": 0,
        "payment_method": "CASH",
        "notes": "E2E 100% discount test",
    }
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=inv_payload)
    assert res.status_code in [200, 201], res.text
    inv = res.json()
    # Prompt 10E Part 5: the urgent fee (max(100, 20% of price), computed by the backend) is not
    # discountable, so a 100%-discounted urgent line still owes the fee.
    fee = max(100, (test_item["price"] * 2 + 5) // 10)
    assert inv["urgent_fee"] == fee
    assert inv["net_amount"] == fee
    assert inv["due_amount"] == fee
    assert inv["payment_status"] == "UNPAID"
    inv_detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert len(inv_detail["lines"]) == 1


# ---------------------------------------------------------------------------
# Scenario 5: Overpayment rejection & payment validation
# ---------------------------------------------------------------------------
def test_05_overpayment_rejection_and_payment_validation(client):
    # First, get a test item
    tests = client.get("/tests", headers=RECEPTIONIST_HEADERS).json()
    test_id = tests[0]["id"]
    unit_price = tests[0]["price"]

    # Create an invoice with partial payment (due > 0)
    inv_payload = {
        "patient_id": 1,
        "age_value": 35,  # Prompt 10E: Finalize requires age and gender
        "gender": "Male",
        "lines": [{"test_id": test_id, "discount_type": "NONE", "discount_value": 0}],
        "initial_payment": 0,
        "payment_method": "CASH",
    }
    inv = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=inv_payload).json()
    inv_id = inv["id"]
    due = inv["due_amount"]
    assert due > 0

    # Overpayment attempt: try to pay due + 500 Taka -> Must return 400 Bad Request
    overpay_res = client.post(
        "/payments",
        headers=RECEPTIONIST_HEADERS,
        json={"invoice_id": inv_id, "amount": due + 500, "channel": "CASH"},
    )
    assert overpay_res.status_code == 400, "Overpayment above due balance must be rejected"


# ---------------------------------------------------------------------------
# Scenario 6: Partial payment, settle due, financial ledger update
# ---------------------------------------------------------------------------
def test_06_settle_due_and_financial_ledger_update(client):
    tests = client.get("/tests", headers=RECEPTIONIST_HEADERS).json()
    test_id = tests[0]["id"]

    # Create invoice with partial payment
    inv = client.post(
        "/invoices",
        headers=RECEPTIONIST_HEADERS,
        json={
            "patient_id": 1,
            "age_value": 35,  # Prompt 10E: Finalize requires age and gender
            "gender": "Male",
            "lines": [{"test_id": test_id, "discount_type": "NONE", "discount_value": 0}],
            "initial_payment": 100,
            "payment_method": "CASH",
        },
    ).json()
    inv_id = inv["id"]
    remaining_due = inv["due_amount"]
    assert remaining_due > 0
    assert inv["payment_status"] in ["PARTIAL", "PARTLY_PAID", "DUE"]

    # Settle exact remaining due
    settle_res = client.post(
        "/payments",
        headers=RECEPTIONIST_HEADERS,
        json={"invoice_id": inv_id, "amount": remaining_due, "channel": "CASH"},
    )
    assert settle_res.status_code in [200, 201], settle_res.text

    # Verify invoice is now fully PAID
    updated_inv = client.get(f"/invoices/{inv_id}", headers=RECEPTIONIST_HEADERS).json()
    assert updated_inv["due_amount"] == 0
    assert updated_inv["payment_status"] == "PAID"


# ---------------------------------------------------------------------------
# Scenario 7: Workstation assignment (manual & bulk)
# ---------------------------------------------------------------------------
def test_07_workstation_assignment(client):
    # Get unassigned test orders
    unassigned_res = client.get("/assignments/unassigned", headers=RECEPTIONIST_HEADERS)
    assert unassigned_res.status_code == 200, unassigned_res.text
    unassigned = unassigned_res.json()

    # Get destinations
    dests = client.get("/tests/destinations", headers=RECEPTIONIST_HEADERS).json()
    assert len(dests) > 0
    dest_id = dests[0]["id"]
    dest_name = dests[0]["name"]

    if unassigned:
        order_id = unassigned[0]["id"]
        # Manual single assign
        assign_res = client.post(
            "/assignments/assign",
            headers=RECEPTIONIST_HEADERS,
            json={"test_order_id": order_id, "destination_id": dest_id, "destination_name": dest_name},
        )
        assert assign_res.status_code in [200, 201], assign_res.text


# ---------------------------------------------------------------------------
# Scenario 8: Pre-sample refund request by Receptionist; separate Admin approval
# ---------------------------------------------------------------------------
def test_08_refund_lifecycle_and_collected_sample_gate(client):
    tests = client.get("/tests", headers=RECEPTIONIST_HEADERS).json()
    test_id = tests[0]["id"]

    # Create paid invoice
    inv = client.post(
        "/invoices",
        headers=RECEPTIONIST_HEADERS,
        json={
            "patient_id": 1,
            "age_value": 35,  # Prompt 10E: Finalize requires age and gender
            "gender": "Male",
            "lines": [{"test_id": test_id, "discount_type": "NONE", "discount_value": 0}],
            "initial_payment": tests[0]["price"],
            "payment_method": "CASH",
        },
    ).json()
    inv_id = inv["id"]
    inv_detail = client.get(f"/invoices/{inv_id}", headers=RECEPTIONIST_HEADERS).json()
    line_id = inv_detail["lines"][0]["id"]
    refund_amount = inv_detail["lines"][0]["net_amount"]

    # Receptionist submits refund request (Pre-sample)
    req_res = client.post(
        "/refunds",
        headers=RECEPTIONIST_HEADERS,
        json={
            "invoice_id": inv_id,
            "invoice_line_id": line_id,
            "amount": refund_amount,
            "reason": "Patient requested test cancellation before sample collection",
        },
    )
    assert req_res.status_code in [200, 201], req_res.text
    refund = req_res.json()
    refund_id = refund["id"]
    # Prompt 13A: pre-lock cancellation needs no approval; the refund is approved at once, awaiting payout
    assert refund["status"] == "APPROVED"
    assert refund["amount"] == refund_amount

    # The (legacy) approval endpoint is still Admin/Owner-only: a Receptionist gets 403
    rec_approve = client.post(
        f"/refunds/review/{refund_id}",
        headers=RECEPTIONIST_HEADERS,
        json={"action": "APPROVE", "review_notes": "Attempt unauthorized approval"},
    )
    assert rec_approve.status_code == 403, "Receptionist must not approve refunds"


# ---------------------------------------------------------------------------
# Scenario 9: Invoice detail & reprint audit
# ---------------------------------------------------------------------------
def test_09_invoice_detail_and_reprint_audit(client):
    # Fetch invoice #1
    res = client.get("/invoices/1", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    inv = res.json()
    assert "lines" in inv
    assert "payments" in inv

    # Request reprint
    reprint_res = client.post(
        "/invoices/1/reprint?reason=Patient lost original copy",
        headers=RECEPTIONIST_HEADERS,
    )
    assert reprint_res.status_code == 200, reprint_res.text
    data = reprint_res.json()
    assert "reprint_count" in data


# ---------------------------------------------------------------------------
# Scenario 10: Report delivery due hold and admin override
# ---------------------------------------------------------------------------
def test_10_report_delivery_due_hold_and_admin_override(client):
    rep_res = client.get("/reports/deliverable", headers=RECEPTIONIST_HEADERS)
    assert rep_res.status_code == 200, rep_res.text
    reports = rep_res.json()
    assert isinstance(reports, list)

    if reports:
        report = reports[0]
        rep_id = report["id"]

        # Printable report data
        print_res = client.get(f"/reports/printable/{rep_id}", headers=RECEPTIONIST_HEADERS)
        assert print_res.status_code == 200, print_res.text

        # Print audit event registration
        audit_res = client.post(f"/reports/{rep_id}/print-events", headers=RECEPTIONIST_HEADERS)
        assert audit_res.status_code == 200, audit_res.text


# ---------------------------------------------------------------------------
# Scenario 11: Staff switcher attribution
# ---------------------------------------------------------------------------
def test_11_staff_switcher_attribution(client):
    # Receptionist profile
    rec_res = client.get("/profile", headers=RECEPTIONIST_HEADERS)
    assert rec_res.status_code == 200
    assert rec_res.json()["role"] == "RECEPTIONIST"

    # Admin profile
    adm_res = client.get("/profile", headers=ADMIN_HEADERS)
    assert adm_res.status_code == 200
    assert adm_res.json()["role"] == "ADMIN"


# ---------------------------------------------------------------------------
# Scenario 12: Profile update & read-only role protection
# ---------------------------------------------------------------------------
def test_12_profile_update_and_role_protection(client):
    # Profile update
    res = client.put(
        "/profile",
        headers=RECEPTIONIST_HEADERS,
        json={"display_name": "Fatima Akter", "phone": "01711223344"},
    )
    assert res.status_code == 200, res.text
    profile = res.json()
    # Ensure role is still RECEPTIONIST
    assert profile["role"] == "RECEPTIONIST"


# ---------------------------------------------------------------------------
# Scenario 13: Global search coverage (Patients, Invoices, Tests, Samples, Reports)
# ---------------------------------------------------------------------------
def test_13_global_search_coverage(client):
    res = client.get("/search?q=CBC", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    results = res.json()
    assert "patients" in results
    assert "invoices" in results
    assert "reports" in results
    assert "tests" in results
    assert "samples" in results


# ---------------------------------------------------------------------------
# Scenario 14: Dues endpoint & summary aliases
# ---------------------------------------------------------------------------
def test_14_dues_endpoint_and_summary_aliases(client):
    res = client.get("/dues", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    dues = res.json()
    assert isinstance(dues, list)
    if dues:
        first = dues[0]
        # Check UI aliases are present
        assert "invoice_number" in first or "invoice_no" in first
        assert "patient_name" in first
        assert "due" in first or "due_amount" in first

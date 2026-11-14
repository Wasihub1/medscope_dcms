"""
Prompt 10E Parts 2-5 — sample rule, age/gender in the invoice payload, payment channels
(ROCKET, OTHER) and the backend urgent fee. Runs only against medscope_test (conftest guard).
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from backend.app.core.payment_channels import PAYMENT_CHANNELS
from backend.app.core.samples import requires_sample
from backend.app.models.invoice import Invoice
from backend.app.models.patient import Patient
from backend.app.models.payment import Payment
from backend.app.models.test import Test
from backend.app.models.visit import Visit
from backend.app.services.invoice_service import compute_urgent_fee
from tests.conftest import ADMIN_HEADERS, RECEPTIONIST_HEADERS


def _tid(db, code):
    return db.execute(select(Test.id).where(Test.code == code)).scalar_one()


def _pid(db):
    return db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()


def _payload(db, codes, paid=0, method="CASH", urgent=(), demographics=True, **extra):
    body = {
        "patient_id": _pid(db),
        "lines": [{"test_id": _tid(db, c), "urgent": c in urgent} for c in codes],
        "initial_payment_amount": paid,
        "initial_payment_method": method,
    }
    if demographics:
        body.update({"age_value": 40, "gender": "Female"})
    body.update(extra)
    return body


def _invoice(client, db, codes, **kw):
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_payload(db, codes, **kw))
    assert res.status_code == 201, res.text
    return res.json()


def _order_id(db, invoice_id, code):
    db.expire_all()
    inv = db.get(Invoice, invoice_id)
    return next(l.test_order.id for l in inv.lines if l.test_code_snapshot == code)


def _ref():
    return "REF" + uuid4().hex[:10].upper()


# ---------------------------------------------------------------------------
# Part 2 — sample_type "None" means no sample
# ---------------------------------------------------------------------------
def test_requires_sample_helper_rules():
    # Prompt 10F (owner decision A5) superseded the 10E rule: NULL / empty sample_type on a
    # non-imaging test now means "unknown" and therefore requires a sample. Only explicit markers
    # mean "no sample". Full 10F coverage: tests/test_prompt10f_owner_findings.py.
    lab = dict(requires_doctor=False, performing_role="LAB_TECH", report_template="NUMERIC_TABLE", department="Hematology", lab_section=None)
    for value in ("None", "none", "N/A", "n/a", "  NONE ", "NA", "No sample"):
        assert requires_sample(SimpleNamespace(sample_type=value, **lab)) is False
    for value in (None, "", "   "):
        assert requires_sample(SimpleNamespace(sample_type=value, **lab)) is True
    assert requires_sample(SimpleNamespace(sample_type="Whole Blood (EDTA)", **lab)) is True
    usg = dict(lab, requires_doctor=True, performing_role="DOCTOR", report_template="NARRATIVE", department="Ultrasonogram")
    assert requires_sample(SimpleNamespace(sample_type="Blood", **usg)) is False  # imaging never needs a sample


def test_none_strings_were_normalized_by_the_migration(db_session):
    # Prompt 10F: explicit markers are meaningful again ("None" = no sample). The 10F tests add probe
    # tests (code P10F_...) carrying them on purpose; the migration check covers every other row.
    n = db_session.execute(text(
        "SELECT count(*) FROM tests WHERE lower(trim(sample_type)) IN ('none', 'n/a', '') AND code NOT LIKE 'P10F\\_%'"
    )).scalar_one()
    assert n == 0


def test_usg_and_xray_proceed_without_a_sample(client, db_session):
    inv = _invoice(client, db_session, ["USG_W_A", "XRAY_CHEST"])
    for code in ("USG_W_A", "XRAY_CHEST"):
        oid = _order_id(db_session, inv["id"], code)
        item = next(i for i in client.get("/worklist", headers=ADMIN_HEADERS, params={"q": inv["invoice_no"]}).json()
                    if i["test_order_id"] == oid)
        assert item["requires_sample"] is False and item["is_imaging"] is True
        # result entry is not blocked by a missing sample
        assert client.get(f"/worklist/{oid}/result-template", headers=ADMIN_HEADERS).status_code == 200
        done = client.post(f"/worklist/{oid}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"})
        assert done.status_code == 200, done.text
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert all(l["sample_status"] != "Awaiting collection" for l in detail["lines"])


def test_sample_based_test_still_blocked_before_sample_taken(client, db_session):
    inv = _invoice(client, db_session, ["CBC"])
    oid = _order_id(db_session, inv["id"], "CBC")
    assert client.post(f"/worklist/{oid}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"}).status_code == 400
    assert client.get(f"/worklist/{oid}/result-template", headers=ADMIN_HEADERS).status_code == 400
    res = client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={"status": "ENTERED", "items": []})
    assert res.status_code == 409


# ---------------------------------------------------------------------------
# Part 3 — age and gender
# ---------------------------------------------------------------------------
def test_age_gender_round_trip_and_no_default(client, db_session):
    inv = _invoice(client, db_session, ["HGB"], demographics=False, age_value=7, age_unit="months", gender="female")
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert (detail["age_value"], detail["age_unit"], detail["visit_gender"]) == (7, "months", "Female")
    db_session.expire_all()
    visit = db_session.get(Visit, db_session.get(Invoice, inv["id"]).visit_id)
    assert visit.age_days == 210.0
    patient = client.get(f"/patients/{_pid(db_session)}", headers=RECEPTIONIST_HEADERS).json()
    assert patient["gender"] == "Female"
    assert patient["last_age_value"] == 7 and patient["last_age_unit"] == "months"


def test_finalize_requires_age_and_gender_but_draft_does_not(client, db_session):
    for missing in ({"gender": "Male"}, {"age_value": 30}, {}):
        body = _payload(db_session, ["HGB"], demographics=False, **missing)
        res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=body)
        assert res.status_code == 400, res.text
        assert "required to finalize" in res.json()["detail"]
    draft = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=_payload(db_session, ["HGB"], demographics=False))
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]
    assert client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS).status_code == 400
    fixed = _payload(db_session, ["HGB"], demographics=False, age_value=52, gender="Male")
    assert client.put(f"/invoices/{draft_id}/draft", headers=RECEPTIONIST_HEADERS, json=fixed).status_code == 200
    fin = client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS)
    assert fin.status_code == 200, fin.text
    assert fin.json()["age_value"] == 52 and fin.json()["visit_gender"] == "Male"


@pytest.mark.parametrize("extra", [{"age_value": 131}, {"age_value": -1}, {"gender": "X"}, {"age_unit": "weeks"}])
def test_invalid_age_or_gender_rejected(client, db_session, extra):
    body = _payload(db_session, ["HGB"])
    body.update(extra)
    assert client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=body).status_code == 422


# ---------------------------------------------------------------------------
# Part 4 — payment channels
# ---------------------------------------------------------------------------
def _ensure_open_day(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st["is_open"]:
        assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201
        st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    return st


def _received(status_json):
    return {c["channel"]: c["received_amount"] for c in status_json["channels"]}


def test_payment_with_each_channel_and_drawer_totals(client, db_session):
    before = _received(_ensure_open_day(client))
    assert set(PAYMENT_CHANNELS) <= set(before)  # ROCKET and OTHER are listed
    inv = _invoice(client, db_session, ["LIPID"])  # 900, unpaid
    for ch in PAYMENT_CHANNELS:
        body = {"amount": 10, "method": ch}
        if ch != "CASH":
            body["reference"] = _ref()
        if ch == "OTHER":
            body["channel_detail"] = "Upay"
        res = client.post(f"/invoices/{inv['id']}/settle-due", headers=RECEPTIONIST_HEADERS, json=body)
        assert res.status_code == 201, (ch, res.text)
        assert res.json()["method"] == ch
        if ch == "OTHER":
            assert res.json()["channel_detail"] == "Upay"
    after = _received(client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json())
    for ch in PAYMENT_CHANNELS:
        assert after[ch] == before.get(ch, 0) + 10, ch
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert any(p["method"] == "OTHER" and p["channel_detail"] == "Upay" for p in detail["payments"])


def test_other_without_name_rejected_and_card_alias(client, db_session):
    inv = _invoice(client, db_session, ["LIPID"])
    res = client.post(f"/invoices/{inv['id']}/settle-due", headers=RECEPTIONIST_HEADERS,
                      json={"amount": 10, "method": "OTHER", "reference": _ref()})
    assert res.status_code == 400 and "OTHER" in res.json()["detail"]
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS,
                      json=_payload(db_session, ["HGB"], paid=50, method="OTHER", initial_payment_reference=_ref()))
    assert res.status_code == 400
    bad = client.post(f"/invoices/{inv['id']}/settle-due", headers=RECEPTIONIST_HEADERS,
                      json={"amount": 10, "method": "PAYPAL", "reference": _ref()})
    assert bad.status_code == 400
    card = client.post(f"/invoices/{inv['id']}/settle-due", headers=RECEPTIONIST_HEADERS,
                       json={"amount": 10, "method": "CARD", "reference": _ref()})
    assert card.status_code == 201 and card.json()["method"] == "POS_CARD"


def test_refund_channel_rule_with_other(client, db_session):
    inv = _invoice(client, db_session, ["TSH", "CBC"], paid=1000, method="OTHER",
                   initial_payment_reference=_ref(), initial_payment_channel_detail="Upay")
    db_session.expire_all()
    pay = db_session.execute(select(Payment).where(Payment.invoice_id == inv["id"])).scalar_one()
    assert pay.method == "OTHER" and pay.channel_detail == "Upay"
    line_id = next(l["id"] for l in inv["lines"] if l["test_code_snapshot"] == "CBC")
    req = client.post("/refunds", headers=RECEPTIONIST_HEADERS, json={"invoice_id": inv["id"], "invoice_line_id": line_id, "reason": "left"})
    rid = req.json()["id"]
    assert req.json()["status"] == "APPROVED"  # Prompt 13A: pre-lock cancellation has no approval step
    assert client.post(f"/refunds/disburse/{rid}", headers=RECEPTIONIST_HEADERS, json={"method": "CASH"}).status_code == 400
    assert client.post(f"/refunds/disburse/{rid}", headers=RECEPTIONIST_HEADERS, json={"method": "OTHER"}).status_code == 400
    ok = client.post(f"/refunds/disburse/{rid}", headers=RECEPTIONIST_HEADERS, json={"method": "OTHER", "reference": _ref()})
    assert ok.status_code == 200, ok.text


# ---------------------------------------------------------------------------
# Part 5 — urgent fee computed by the backend
# ---------------------------------------------------------------------------
def test_urgent_fee_formula_matches_the_ui_rule():
    # UI: Math.max(100, Math.round(price * 0.2)) -> 20% of price, half up, minimum 100
    assert compute_urgent_fee(150) == 100
    assert compute_urgent_fee(500) == 100
    assert compute_urgent_fee(502) == 100   # 100.4
    assert compute_urgent_fee(503) == 101   # 100.6
    assert compute_urgent_fee(600) == 120
    assert compute_urgent_fee(1200) == 240


def test_urgent_fee_with_and_without_and_minimum(client, db_session):
    plain = _invoice(client, db_session, ["HGB", "TSH"])
    assert plain["urgent_fee"] == 0 and plain["net_amount"] == 750
    urgent = _invoice(client, db_session, ["HGB", "TSH"], urgent=("HGB", "TSH"))
    assert urgent["urgent_fee"] == 100 + 120  # HGB 150 -> minimum 100; TSH 600 -> 120
    assert urgent["net_amount"] == 750 + 220 and urgent["due_amount"] == 970
    fees = {l["test_code_snapshot"]: l["line_urgent_fee"] for l in urgent["lines"]}
    assert fees == {"HGB": 100, "TSH": 120}


def test_urgent_fee_preview_equals_saved_and_client_fee_ignored(client, db_session):
    body = _payload(db_session, ["CBC", "LIPID"], urgent=("LIPID",), master_discount_type="PERCENT", master_discount_value=10)
    body["urgent_fee"] = 1  # never trusted
    body["lines"][1]["urgent_fee"] = 1
    draft = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=body).json()
    fin = client.post(f"/invoices/{draft['id']}/finalize", headers=RECEPTIONIST_HEADERS).json()
    # gross 1300, 10% master discount 130 (fee not discounted), LIPID fee 180
    assert draft["urgent_fee"] == fin["urgent_fee"] == 180
    assert draft["net_amount"] == fin["net_amount"] == 1300 - 130 + 180
    assert fin["due_amount"] == fin["net_amount"]
    db_session.expire_all()
    assert db_session.execute(select(func.sum(Invoice.urgent_fee)).where(Invoice.id == fin["id"])).scalar_one() == 180

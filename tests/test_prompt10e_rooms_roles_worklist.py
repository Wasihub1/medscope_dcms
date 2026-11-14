"""
Prompt 10E Parts 6, 7 and 9 — roles (LAB_TECH profile, CASHIER release with due, DOCTOR),
room-based routing / visibility / reassignment, and the Ready / report-preview data.
Runs only against medscope_test (conftest guard). Passwords are generated per run.
"""
import secrets
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.lab_sections import section_for_test_fields
from backend.app.core.permissions import MONEY_PERMISSIONS, ROLE_DEFAULTS
from backend.app.models.audit import AuditLog
from backend.app.models.invoice import Invoice
from backend.app.models.patient import Patient
from backend.app.models.report import ReportVersion
from backend.app.models.test import Test, TestDestination
from backend.app.models.test_order import TestOrder
from backend.app.models.user import Staff
from tests.conftest import (
    ADMIN_HEADERS,
    CASHIER_HEADERS,
    OWNER_HEADERS,
    RECEPTIONIST_HEADERS,
    TECH_KAMAL_HEADERS,
    TECH_NASRIN_AUTH_TOKEN,
)

PASSWORD = "R" + secrets.token_urlsafe(16)  # generated per run; never stored
NASRIN_HEADERS = {"Authorization": f"Bearer {TECH_NASRIN_AUTH_TOKEN}", "X-Requested-With": "XMLHttpRequest"}
MONEY_WORDS = ("price", "amount", "net", "gross", "due", "paid", "discount", "commission", "fee", "refund_amount")


def _client():
    from backend.app.main import app
    return TestClient(app, base_url="http://testserver/api/v1", headers={"X-Requested-With": "XMLHttpRequest"})


def _new_user(role, creator=ADMIN_HEADERS, **extra):
    body = {"username": f"{role.lower()}_{uuid4().hex[:8]}", "display_name": f"P10E {role}", "password": PASSWORD, "role": role}
    body.update(extra)
    return _client().post("/users", headers=creator, json=body)


def _login(username):
    c = _client()
    res = c.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return c


def _pid(db):
    return db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()


def _invoice(client, db, codes, paid=0):
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json={
        "patient_id": _pid(db), "age_value": 30, "gender": "Male",
        "lines": [{"test_id": db.execute(select(Test.id).where(Test.code == c)).scalar_one()} for c in codes],
        "initial_payment_amount": paid, "initial_payment_method": "CASH",
    })
    assert res.status_code == 201, res.text
    return res.json()


def _order(db, invoice_id, code):
    db.expire_all()
    inv = db.get(Invoice, invoice_id)
    return next(l.test_order for l in inv.lines if l.test_code_snapshot == code)


def _ids(c_or_client, headers=None, **params):
    res = c_or_client.get("/worklist", headers=headers, params={"limit": 200, **params}) if headers else c_or_client.get("/worklist", params={"limit": 200, **params})
    assert res.status_code == 200, res.text
    return {i["test_order_id"] for i in res.json()}


def _no_money(d):
    return not any(any(w in k.lower() for w in MONEY_WORDS) for k in d.keys())


# ---------------------------------------------------------------------------
# Part 7.1 — test -> room mapping
# ---------------------------------------------------------------------------
def test_catalog_values_map_to_rooms(db_session):
    cases = [
        (("Hematology", None, "Hematopathologist"), "HEMATOLOGY"),
        (("Biochemistry", None, "Clinical Biochemist"), "BIOCHEMISTRY"),
        (("Biochemical Tests", "Biochemistry Room 102", "LAB_TECH"), "BIOCHEMISTRY"),
        (("Serology", "Biochemistry Room 102", "LAB_TECH"), "BIOCHEMISTRY"),
        (("Microbiology & Parasitology", None, "Microbiologist"), "MICROBIOLOGY"),
        (("Microbiology", "Microbiology Lab 105", "LAB_TECH"), "MICROBIOLOGY"),
        (("Ultrasonography (USG)", None, "USG Technician / Radiologist"), "ULTRASONOGRAPHY"),
        (("Ultrasonogram", "Ultrasonography Room 204", "DOCTOR"), "ULTRASONOGRAPHY"),
        (("X-Ray & Radiology", None, "Radiologist / Radiographer (X-Ray Tech)"), None),
        (("Clinical Pathology", None, "Specialist Doctor / Designated Lab Technologist"), None),
    ]
    for args, expected in cases:
        assert section_for_test_fields(*args) == expected, args
    urine_cs = db_session.execute(select(Test).where(Test.code == "URINE_C_S")).scalar_one()
    assert urine_cs.lab_section == "MICROBIOLOGY"  # backfilled by the migration
    catalog = _client().get("/tests", headers=RECEPTIONIST_HEADERS, params={"q": "URINE_C_S"}).json()
    assert catalog[0]["lab_section"] == "MICROBIOLOGY"


# ---------------------------------------------------------------------------
# Part 7.2-7.3 — routing and visibility
# ---------------------------------------------------------------------------
def test_order_routes_to_room_and_every_room_technician_sees_it(client, db_session):
    second = _new_user("LAB_TECH", lab_section="HEMATOLOGY")
    assert second.status_code == 201, second.text
    c2 = _login(second.json()["username"])
    inv = _invoice(client, db_session, ["CBC"])
    order = _order(db_session, inv["id"], "CBC")
    assert order.lab_section == "HEMATOLOGY" and order.status == "ASSIGNED" and order.assigned_to_id is None
    assert order.id in _ids(client, TECH_KAMAL_HEADERS)
    assert order.id in _ids(c2)
    assert order.id not in _ids(client, NASRIN_HEADERS)        # other room
    assert order.id in _ids(client, ADMIN_HEADERS, q=inv["invoice_no"])  # filtered by bill: the test DB holds >200 urgent orders
    # the second technician can act; the first still sees the order afterwards
    res = c2.post(f"/worklist/{order.id}/sample-taken", json={})
    assert res.status_code == 200, res.text
    assert res.json()["assigned_to_id"] == second.json()["id"]
    assert order.id in _ids(client, TECH_KAMAL_HEADERS)
    # a technician of another room cannot act on it
    assert client.post(f"/worklist/{order.id}/status", headers=NASRIN_HEADERS, json={"status": "COMPLETED"}).status_code == 403
    # money stays hidden from technicians
    item = next(i for i in c2.get("/worklist", params={"q": inv["invoice_no"]}).json() if i["test_order_id"] == order.id)
    assert _no_money(item)


def test_empty_room_is_unassigned_then_released_when_a_technician_joins(client, db_session):
    # Make the Ultrasonography room empty (test DB only) and use a non-doctor test mapped to it
    for s in db_session.execute(select(Staff).where(Staff.role == "LAB_TECH", Staff.lab_section == "ULTRASONOGRAPHY")).scalars():
        s.active = False
    code = f"P10E_{uuid4().hex[:6].upper()}"
    db_session.add(Test(tenant_id="center-seba-01", code=code, name=f"Room probe {code}", department="Ultrasonography (USG)",
                        price=300, sample_type=None, performing_role="USG Technician", requires_doctor=False,
                        report_template="NUMERIC_TABLE", approval_rule="TECHNICIAN_FINAL", is_outsourced=False, active=True))
    db_session.commit()
    inv = _invoice(client, db_session, [code])
    order = _order(db_session, inv["id"], code)
    assert order.lab_section == "ULTRASONOGRAPHY" and order.status == "UNASSIGNED"
    assert order.id in _ids(client, ADMIN_HEADERS, q=inv["invoice_no"])
    assert order.id in _ids(client, OWNER_HEADERS, q=inv["invoice_no"])
    assert order.id not in _ids(client, TECH_KAMAL_HEADERS)
    tech = _new_user("LAB_TECH", lab_section="ULTRASONOGRAPHY")
    assert tech.status_code == 201, tech.text
    db_session.expire_all()
    assert db_session.get(TestOrder, order.id).status == "ASSIGNED"
    assert db_session.execute(select(AuditLog).where(
        AuditLog.action == "ORDER_ROOM_RELEASED", AuditLog.entity_id == str(order.id))).scalars().first() is not None
    assert order.id in _ids(_login(tech.json()["username"]))


def test_reassign_moves_room_before_completed_and_is_refused_after(client, db_session):
    inv = _invoice(client, db_session, ["HGB"])
    order = _order(db_session, inv["id"], "HGB")
    assert order.lab_section == "HEMATOLOGY"
    assert client.post(f"/worklist/{order.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    # technicians and front desk do not hold worklist.reassign by default
    assert client.post(f"/worklist/{order.id}/reassign", headers=TECH_KAMAL_HEADERS, json={"lab_section": "BIOCHEMISTRY"}).status_code == 403
    assert client.post(f"/worklist/{order.id}/reassign", headers=RECEPTIONIST_HEADERS, json={"lab_section": "BIOCHEMISTRY"}).status_code == 403
    res = client.post(f"/worklist/{order.id}/reassign", headers=ADMIN_HEADERS, json={"lab_section": "BIOCHEMISTRY", "reason": "analyser down"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["lab_section"] == "BIOCHEMISTRY" and body["sample_status"] == "COLLECTED"  # sample kept
    assert order.id in _ids(client, NASRIN_HEADERS) and order.id not in _ids(client, TECH_KAMAL_HEADERS)
    db_session.expire_all()
    audit = db_session.execute(select(AuditLog).where(AuditLog.action == "REASSIGN_ROOM", AuditLog.entity_id == str(order.id))).scalars().first()
    assert audit is not None and "HEMATOLOGY" in audit.before_value and "analyser down" in audit.after_value
    assert client.post(f"/worklist/{order.id}/status", headers=NASRIN_HEADERS, json={"status": "COMPLETED"}).status_code == 200
    late = client.post(f"/worklist/{order.id}/reassign", headers=ADMIN_HEADERS, json={"lab_section": "HEMATOLOGY"})
    assert late.status_code == 409


def test_assign_tests_page_stores_room_names_not_ids(client, db_session):
    inv = _invoice(client, db_session, ["URINE"])  # Clinical Pathology -> no room -> UNASSIGNED
    order = _order(db_session, inv["id"], "URINE")
    assert order.status == "UNASSIGNED" and order.lab_section is None
    micro = db_session.execute(select(TestDestination).where(TestDestination.name == "Microbiology Lab 105")).scalars().first()
    assert client.post("/assignments/assign", headers=RECEPTIONIST_HEADERS,
                       json={"test_order_id": order.id, "destination_id": 999999}).status_code == 400
    res = client.post("/assignments/assign", headers=RECEPTIONIST_HEADERS,
                      json={"test_order_id": order.id, "destination_id": micro.id})
    assert res.status_code == 200, res.text
    db_session.expire_all()
    o = db_session.get(TestOrder, order.id)
    assert o.lab_section == "MICROBIOLOGY" and o.assigned_destination == "Microbiology Lab 105"
    assert not (o.assigned_destination or "").isdigit() and o.assigned_to_id is None
    # moving an already-routed order needs worklist.reassign
    again = client.post("/assignments/assign", headers=RECEPTIONIST_HEADERS,
                        json={"test_order_id": order.id, "lab_section": "HEMATOLOGY"})
    assert again.status_code == 403
    rooms = client.get("/worklist/rooms", headers=RECEPTIONIST_HEADERS).json()
    assert {r["code"] for r in rooms} == {"HEMATOLOGY", "BIOCHEMISTRY", "MICROBIOLOGY", "ULTRASONOGRAPHY"}


# ---------------------------------------------------------------------------
# Part 7.7 — a technician needs a room; DOCTOR has none
# ---------------------------------------------------------------------------
def test_lab_tech_requires_a_room(client, db_session):
    res = _new_user("LAB_TECH")
    assert res.status_code == 400 and "lab room" in res.json()["detail"]
    rec = _new_user("RECEPTIONIST").json()
    assert client.put(f"/users/{rec['id']}/role", headers=ADMIN_HEADERS, json={"role": "LAB_TECH"}).status_code == 400
    assert client.put(f"/users/{rec['id']}/role", headers=ADMIN_HEADERS, json={"role": "LAB_TECH", "lab_section": "MICROBIOLOGY"}).status_code == 200
    assert _new_user("DOCTOR", lab_section="HEMATOLOGY").status_code == 400


# ---------------------------------------------------------------------------
# Part 6 — roles and permissions
# ---------------------------------------------------------------------------
def test_lab_tech_reads_and_edits_only_own_profile(client, db_session):
    me = client.get("/profile/me", headers=TECH_KAMAL_HEADERS)
    assert me.status_code == 200 and me.json()["username"] == "tech_kamal"
    upd = client.put("/profile/me", headers=TECH_KAMAL_HEADERS, json={"display_name": me.json()["display_name"], "phone": me.json()["phone"]})
    assert upd.status_code == 200 and upd.json()["username"] == "tech_kamal"
    other = db_session.execute(select(Staff).where(Staff.username == "tech_nasrin")).scalar_one()
    assert client.patch(f"/users/{other.id}", headers=TECH_KAMAL_HEADERS, json={"display_name": "x"}).status_code == 403
    assert "profile.manage" in client.get("/auth/me", headers=TECH_KAMAL_HEADERS).json()["permissions"]


def test_cashier_and_receptionist_cannot_release_report_with_due(client, db_session):
    rv = db_session.execute(
        select(ReportVersion).join(ReportVersion.test_order).join(TestOrder.invoice_line)
        .join(Invoice, Invoice.id == TestOrder.invoice_line.property.mapper.class_.invoice_id)
        .where(Invoice.due > 0, ReportVersion.authorized == True)  # noqa: E712
    ).scalars().first()
    assert rv is not None, "seed provides a ready report held by a due"
    body = {"delivered_to_name": "Patient", "delivered_to_relation": "Self", "admin_due_override_reason": "Promised to pay"}
    for headers in (CASHIER_HEADERS, RECEPTIONIST_HEADERS):
        assert client.post(f"/reports/deliver/{rv.id}", headers=headers, json=body).status_code == 403
    no_reason = dict(body, admin_due_override_reason=None)
    assert client.post(f"/reports/deliver/{rv.id}", headers=ADMIN_HEADERS, json=no_reason).status_code == 400
    assert client.post(f"/reports/deliver/{rv.id}", headers=OWNER_HEADERS, json=body).status_code == 201
    assert "report.release_with_due" not in client.get("/auth/me", headers=CASHIER_HEADERS).json()["permissions"]


def test_doctor_defaults_queue_and_money_restriction(client, db_session):
    doc = _new_user("DOCTOR", creator=OWNER_HEADERS)
    assert doc.status_code == 201, doc.text
    assert doc.json()["lab_section"] is None
    c = _login(doc.json()["username"])
    me = c.get("/auth/me").json()
    assert set(me["permissions"]) == set(ROLE_DEFAULTS["DOCTOR"])
    assert not (set(me["permissions"]) & MONEY_PERMISSIONS)
    assert me["home_route"] == "/dashboard"
    for path in ("/invoices", "/dashboard", "/dues", "/refunds", "/business-day/status"):
        assert c.get(path).status_code == 403, path
    inv = _invoice(client, db_session, ["USG_W_A", "CBC"])
    usg = _order(db_session, inv["id"], "USG_W_A")
    cbc = _order(db_session, inv["id"], "CBC")
    assert usg.status == "AWAITING_DOCTOR" and usg.lab_section == "ULTRASONOGRAPHY"
    queue = c.get("/worklist", params={"q": inv["invoice_no"]}).json()
    assert {i["test_order_id"] for i in queue} == {usg.id}  # doctor queue only, not the CBC
    assert all(_no_money(i) for i in queue)
    assert c.post(f"/worklist/{cbc.id}/status", json={"status": "COMPLETED"}).status_code == 403
    done = c.post(f"/worklist/{usg.id}/status", json={"status": "COMPLETED"})
    assert done.status_code == 200, done.text
    # an override can never give DOCTOR a money key
    res = client.put(f"/users/{doc.json()['id']}/permissions", headers=OWNER_HEADERS, json={"overrides": {"invoice.view": True}})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Part 9 — saved result: preview data and Ready reports
# ---------------------------------------------------------------------------
def test_saved_result_exposes_preview_data_and_ready_filter(client, db_session):
    inv = _invoice(client, db_session, ["HGB"])
    order = _order(db_session, inv["id"], "HGB")
    assert client.post(f"/worklist/{order.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    save = client.post(f"/worklist/{order.id}/result", headers=TECH_KAMAL_HEADERS, json={
        "status": "ENTERED", "items": [{"component_code": "HGB", "component_name": "Hemoglobin (Hb%)", "value": "13.1"}]})
    assert save.status_code == 200, save.text
    rows = client.get("/worklist", headers=TECH_KAMAL_HEADERS, params={"q": inv["invoice_no"]}).json()
    row = next(i for i in rows if i["test_order_id"] == order.id)
    assert row["has_result"] is True and row["result_status"] == "ENTERED"
    assert row["status"] == "COMPLETED" and row["report_ready"] is True
    ready = _ids(client, TECH_KAMAL_HEADERS, status="READY")
    assert order.id in ready
    summary = client.get("/worklist/summary", headers=TECH_KAMAL_HEADERS).json()
    assert summary["ready_count"] >= 1 and _no_money(summary)
    preview = client.get(f"/worklist/{order.id}/result", headers=TECH_KAMAL_HEADERS)
    assert preview.status_code == 200
    data = preview.json()
    assert data["existing_result"]["items"][0]["value"] == "13.1"
    assert data["patient_age"] == "30 years" and data["patient_gender"]
    assert _no_money(data) and _no_money(data["existing_result"])

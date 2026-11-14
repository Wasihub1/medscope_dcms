"""
Prompt 15 (D22) - doctor sign-off: the approval queue and the approval action.

Covers: the queue (rule + ENTERED + not yet approved), Path A (Admin/Owner on a doctor's behalf, with
attestation), Path B (the DOCTOR login for its own assigned orders), scoping by assignment, role gating,
the approval record beside the technician sign-off, the audit distinction, and the order moving on.
Runs only against medscope_test (conftest guard).
"""
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.core.permissions import PERMISSIONS, ROLE_DEFAULTS, has_permission
from backend.app.models.audit import AuditLog
from backend.app.models.doctor_approval import DoctorApproval
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.test import Test
from backend.app.models.test_order import TestOrder
from backend.app.models.user import Staff
from tests.conftest import (
    ADMIN_HEADERS, CASHIER_HEADERS, DOCTOR_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS,
)

TENANT = "center-seba-01"
BASE = "/doctor-approvals"


# ---------------------------------------------------------------- helpers
def _probe_test(db, rule, **kw):
    code = f"P15_{uuid4().hex[:8].upper()}"
    doctor_routed = rule == "DOCTOR_REQUIRED"
    fields = dict(tenant_id=TENANT, code=code, name=f"15 probe {code}", department="Radiology", price=300,
                  sample_type=None, performing_role="DOCTOR" if doctor_routed else "LAB_TECH", requires_doctor=doctor_routed,
                  report_template="NARRATIVE", approval_rule=rule, is_outsourced=False, active=True,
                  lab_section="ULTRASONOGRAPHY")
    fields.update(kw)
    t = Test(**fields)
    db.add(t)
    db.commit()
    return t.id


def _open_day(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st["is_open"]:
        assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201


def _order(client, db, rule="DOCTOR_REQUIRED", result="ENTERED", **kw):
    """A probe order of the given approval rule; result = 'ENTERED', 'DRAFT' or None."""
    tid = _probe_test(db, rule, **kw)
    _open_day(client)
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json={
        "patient_id": pid, "age_value": 30, "gender": "Male", "lines": [{"test_id": tid}],
        "initial_payment_amount": 0, "initial_payment_method": "CASH",
    })
    assert res.status_code == 201, res.text
    db.expire_all()
    order = db.get(Invoice, res.json()["id"]).lines[0].test_order
    oid = order.id
    if result:
        r = client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={
            "status": result, "findings": "Normal study.", "impression": "No abnormality seen."})
        assert r.status_code == 200, r.text
    db.expire_all()
    return oid


def _doctor(client, name_prefix="Dr Probe", reg="BMDC-A-12345", rtype="Doctor"):
    res = client.post("/referrers", headers=RECEPTIONIST_HEADERS, json={
        "name": f"{name_prefix} {uuid4().hex[:6]}", "referrer_type": rtype, "registration_no": reg, "specialty": "Radiology"})
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def _my_profile_id(db):
    db.expire_all()
    return db.execute(select(Staff.doctor_profile_id).where(Staff.username == "doctor_rahim")).scalar_one()


def _approval(db, oid):
    db.expire_all()
    return db.execute(select(DoctorApproval).where(DoctorApproval.test_order_id == oid)).scalar_one_or_none()


def _queue_ids(client, headers, **params):
    res = client.get(BASE + "/queue", headers=headers, params={"limit": 1000, **params})
    assert res.status_code == 200, res.text
    return {i["test_order_id"] for i in res.json()["items"]}, res.json()


# ---------------------------------------------------------------- permissions
def test_permission_key_reused_and_role_matrix():
    # no new permission key (Prompt 14 left it at 39); the existing key covers exactly Admin, Owner, Doctor
    assert len(PERMISSIONS) == 43
    holders = {r for r, perms in ROLE_DEFAULTS.items() if "result.complete_doctor_routed" in perms}
    assert holders == {"OWNER", "ADMIN", "DOCTOR"}


@pytest.mark.parametrize("headers", [RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS])
def test_other_roles_get_403_everywhere(client, db_session, headers):
    oid = _order(client, db_session)
    assert client.get(BASE + "/queue", headers=headers).status_code == 403
    assert client.get(f"{BASE}/{oid}", headers=headers).status_code == 403
    assert client.post(f"{BASE}/{oid}/approve", headers=headers, json={"doctor_id": 1, "attestation": True}).status_code == 403
    assert client.post(f"{BASE}/{oid}/assign-doctor", headers=headers, json={"doctor_id": 1}).status_code == 403
    assert _approval(db_session, oid) is None


def test_non_doctor_role_with_granted_key_is_still_refused(client, db_session):
    """Role guard: a per-user override on the key does not let a Lab Tech attest for a doctor."""
    from backend.app.models.user import StaffPermissionOverride
    kamal = db_session.execute(select(Staff).where(Staff.username == "tech_kamal")).scalar_one()
    db_session.add(StaffPermissionOverride(tenant_id=TENANT, staff_id=kamal.id, permission_key="result.complete_doctor_routed", granted=True))
    db_session.commit()
    try:
        # the session actor is rebuilt from the DB on every request
        assert client.get(BASE + "/queue", headers=TECH_KAMAL_HEADERS).status_code == 403
    finally:
        for o in db_session.execute(select(StaffPermissionOverride).where(StaffPermissionOverride.staff_id == kamal.id)).scalars().all():
            db_session.delete(o)
        db_session.commit()


# ---------------------------------------------------------------- queue
def test_queue_lists_only_entered_doctor_rule_orders_without_approval(client, db_session):
    entered = _order(client, db_session, "DOCTOR_REQUIRED")
    both = _order(client, db_session, "BOTH_SIGNATURES")
    draft = _order(client, db_session, "DOCTOR_REQUIRED", result="DRAFT")
    none = _order(client, db_session, "DOCTOR_REQUIRED", result=None)
    tech_final = _order(client, db_session, "TECHNICIAN_FINAL", performing_role="LAB_TECH", requires_doctor=False)
    ids, body = _queue_ids(client, ADMIN_HEADERS)
    assert body["scope"] == "ALL"
    assert entered in ids and both in ids
    assert draft not in ids and none not in ids and tech_final not in ids
    item = next(i for i in body["items"] if i["test_order_id"] == both)
    assert item["approval_rule"] == "BOTH_SIGNATURES" and item["technician_name"]
    for key in item:
        assert "price" not in key and "due" not in key and "amount" not in key  # money-free
    # Owner sees the same set
    assert {entered, both} <= _queue_ids(client, OWNER_HEADERS)[0]


def test_admin_can_filter_the_queue_by_doctor(client, db_session):
    d1, d2 = _doctor(client), _doctor(client)
    a, b = _order(client, db_session), _order(client, db_session)
    assert client.post(f"{BASE}/{a}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": d1}).status_code == 200
    assert client.post(f"{BASE}/{b}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": d2}).status_code == 200
    assert _queue_ids(client, ADMIN_HEADERS, doctor_id=d1)[0] == {a}
    assert _queue_ids(client, ADMIN_HEADERS, doctor_id=d2)[0] == {b}
    log = db_session.execute(select(AuditLog).where(AuditLog.action == "DOCTOR_APPROVAL_ASSIGNED", AuditLog.entity_id == str(a))).scalars().first()
    assert log is not None and log.acting_role == "ADMIN"


def test_doctor_login_sees_only_its_own_assigned_orders(client, db_session):
    mine = _my_profile_id(db_session)
    other = _doctor(client)
    own_o, other_o, unassigned = _order(client, db_session), _order(client, db_session), _order(client, db_session)
    assert client.post(f"{BASE}/{own_o}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": mine}).status_code == 200
    assert client.post(f"{BASE}/{other_o}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": other}).status_code == 200
    ids, body = _queue_ids(client, DOCTOR_HEADERS)
    assert body["scope"] == "OWN" and body["my_doctor"]["id"] == mine
    assert own_o in ids and other_o not in ids and unassigned not in ids
    # a doctor cannot widen the scope with the filter
    assert other_o not in _queue_ids(client, DOCTOR_HEADERS, doctor_id=other)[0]
    # ... nor open or approve another doctor's order, nor an unassigned one
    for oid in (other_o, unassigned):
        assert client.get(f"{BASE}/{oid}", headers=DOCTOR_HEADERS).status_code == 403
        assert client.post(f"{BASE}/{oid}/approve", headers=DOCTOR_HEADERS, json={}).status_code == 403
        assert _approval(db_session, oid) is None
    # a doctor cannot assign orders
    assert client.post(f"{BASE}/{own_o}/assign-doctor", headers=DOCTOR_HEADERS, json={"doctor_id": mine}).status_code == 403


# ---------------------------------------------------------------- detail
def test_detail_shows_result_rule_doctor_and_technician_signoff(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "BOTH_SIGNATURES")
    client.post(f"{BASE}/{oid}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": doc})
    d = client.get(f"{BASE}/{oid}", headers=ADMIN_HEADERS).json()
    assert d["approval_rule"] == "BOTH_SIGNATURES" and d["path"] == "STAFF_ATTESTATION" and d["can_approve"] is True
    assert d["assigned_doctor"]["id"] == doc and d["assigned_doctor"]["registration_no"] == "BMDC-A-12345"
    assert d["technician_name"] and d["approval"] is None
    assert d["preview"]["findings"] == "Normal study." and d["preview"]["result_status"] == "ENTERED"


def test_detail_of_a_technician_final_order_is_refused(client, db_session):
    oid = _order(client, db_session, "TECHNICIAN_FINAL", performing_role="LAB_TECH", requires_doctor=False)
    assert client.get(f"{BASE}/{oid}", headers=ADMIN_HEADERS).status_code == 409
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": _doctor(client), "attestation": True}).status_code == 409


# ---------------------------------------------------------------- Path A
def test_path_a_requires_doctor_and_attestation(client, db_session):
    oid = _order(client, db_session)
    doc = _doctor(client)
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"attestation": True}).status_code == 400
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc}).status_code == 400
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": False}).status_code == 400
    assert _approval(db_session, oid) is None  # nothing written by the refused calls


def test_path_a_refuses_doctor_without_registration_or_non_doctor(client, db_session):
    oid = _order(client, db_session)
    no_reg = client.post("/referrers", headers=RECEPTIONIST_HEADERS, json={"name": f"Dr Probe {uuid4().hex[:6]}", "referrer_type": "Doctor"}).json()["id"]
    clinic = _doctor(client, "Probe Clinic", rtype="Clinic")
    r = client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": no_reg, "attestation": True})
    assert r.status_code == 409 and "registration" in r.json()["detail"].lower()
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": clinic, "attestation": True}).status_code == 400
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": 99999999, "attestation": True}).status_code == 404
    assert _approval(db_session, oid) is None


def test_path_a_admin_records_approval_for_visiting_doctor(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "DOCTOR_REQUIRED")
    assert db_session.get(TestOrder, oid).status == "AWAITING_DOCTOR"
    r = client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": True, "notes": "Phone confirmation"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_attestation"] is True and body["approved_by_role"] == "ADMIN" and body["doctor"]["id"] == doc
    row = _approval(db_session, oid)
    admin = db_session.execute(select(Staff).where(Staff.username == "admin_tariq")).scalar_one()
    assert row.approved_by_user_id == admin.id and row.doctor_id == doc and row.is_attestation is True
    assert row.doctor_registration_no == "BMDC-A-12345" and row.notes == "Phone confirmation"
    # the order moved on: AWAITING_DOCTOR -> COMPLETED (existing completion step), line locked, now Ready
    order = db_session.get(TestOrder, oid)
    assert order.status == "COMPLETED" and order.invoice_line.is_locked is True
    # audit distinguishes who clicked from whose approval it is
    log = db_session.execute(select(AuditLog).where(AuditLog.entity_id == str(oid), AuditLog.action == "DOCTOR_APPROVAL_RECORDED_BY_STAFF")).scalar_one()
    assert log.actor_id == admin.id and "on behalf of" in log.after_value and "BMDC-A-12345" in log.after_value
    assert db_session.execute(select(AuditLog).where(AuditLog.entity_id == str(oid), AuditLog.action == "DOCTOR_APPROVED_OWN_RESULT")).first() is None
    # leaves the queue; a second approval is refused
    assert oid not in _queue_ids(client, ADMIN_HEADERS)[0]
    assert client.post(f"{BASE}/{oid}/approve", headers=OWNER_HEADERS, json={"doctor_id": doc, "attestation": True}).status_code == 409


def test_owner_can_use_path_a_too(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session)
    r = client.post(f"{BASE}/{oid}/approve", headers=OWNER_HEADERS, json={"doctor_id": doc, "attestation": True})
    assert r.status_code == 201 and r.json()["approved_by_role"] == "OWNER"


def test_draft_result_cannot_be_approved(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, result="DRAFT")
    r = client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": True})
    assert r.status_code == 409 and _approval(db_session, oid) is None


def test_both_signature_keeps_technician_signoff_and_adds_the_doctor_one(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "BOTH_SIGNATURES")
    order = db_session.get(TestOrder, oid)
    assert order.status == "IN_PROGRESS"  # technician's sign-off done (result submitted), second signature missing
    tech_id, tech_at = order.result.entered_by_id, order.result.entered_at
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": True}).status_code == 201
    db_session.expire_all()
    order = db_session.get(TestOrder, oid)
    # technician sign-off untouched; doctor approval stored beside it and reachable from the same order
    assert order.result.entered_by_id == tech_id and order.result.entered_at == tech_at
    assert order.doctor_approval.doctor_id == doc and order.doctor_approval.approval_rule == "BOTH_SIGNATURES"
    assert order.status == "COMPLETED"
    d = client.get(f"{BASE}/{oid}", headers=ADMIN_HEADERS).json()
    assert d["technician_name"] and d["approval"]["doctor"]["id"] == doc and d["can_approve"] is False


def test_approval_snapshot_survives_a_later_profile_edit(client, db_session):
    from backend.app.models.referrer import Referrer
    doc = _doctor(client)
    oid = _order(client, db_session)
    assert client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": True}).status_code == 201
    ref = db_session.get(Referrer, doc)
    old_name = ref.name
    ref.name, ref.registration_no = "Dr Probe Renamed", "NEW-REG"
    db_session.commit()
    row = _approval(db_session, oid)
    assert row.doctor_name == old_name and row.doctor_registration_no == "BMDC-A-12345"


# ---------------------------------------------------------------- Path B
def test_path_b_doctor_approves_own_assigned_result(client, db_session):
    mine = _my_profile_id(db_session)
    oid = _order(client, db_session)
    assert client.post(f"{BASE}/{oid}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": mine}).status_code == 200
    d = client.get(f"{BASE}/{oid}", headers=DOCTOR_HEADERS).json()
    assert d["path"] == "DOCTOR_OWN" and d["my_doctor"]["id"] == mine and d["can_approve"] is True
    # a doctor cannot pick another doctor or skip anything: doctor_id / attestation in the body are ignored
    r = client.post(f"{BASE}/{oid}/approve", headers=DOCTOR_HEADERS, json={"doctor_id": _doctor(client), "attestation": True, "notes": "ok"})
    assert r.status_code == 201, r.text
    row = _approval(db_session, oid)
    rahim = db_session.execute(select(Staff).where(Staff.username == "doctor_rahim")).scalar_one()
    assert row.doctor_id == mine and row.approved_by_user_id == rahim.id and row.is_attestation is False
    assert row.approved_by_role == "DOCTOR" and row.doctor_registration_no
    assert db_session.get(TestOrder, oid).status == "COMPLETED"
    log = db_session.execute(select(AuditLog).where(AuditLog.entity_id == str(oid), AuditLog.action == "DOCTOR_APPROVED_OWN_RESULT")).scalar_one()
    assert log.actor_id == rahim.id and "approved own result" in log.after_value
    assert db_session.execute(select(AuditLog).where(AuditLog.entity_id == str(oid), AuditLog.action == "DOCTOR_APPROVAL_RECORDED_BY_STAFF")).first() is None
    assert oid not in _queue_ids(client, DOCTOR_HEADERS)[0]


def test_both_paths_attribute_the_same_doctor_identically(client, db_session):
    """Same doctor name + registration on the approval whichever path recorded it."""
    mine = _my_profile_id(db_session)
    a, b = _order(client, db_session), _order(client, db_session)
    client.post(f"{BASE}/{b}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": mine})
    assert client.post(f"{BASE}/{a}/approve", headers=ADMIN_HEADERS, json={"doctor_id": mine, "attestation": True}).status_code == 201
    assert client.post(f"{BASE}/{b}/approve", headers=DOCTOR_HEADERS, json={}).status_code == 201
    ra, rb = _approval(db_session, a), _approval(db_session, b)
    assert (ra.doctor_id, ra.doctor_name, ra.doctor_registration_no) == (rb.doctor_id, rb.doctor_name, rb.doctor_registration_no)
    assert ra.is_attestation is True and rb.is_attestation is False and ra.approved_by_user_id != rb.approved_by_user_id


def test_doctor_login_without_linked_profile_cannot_approve(client, db_session):
    rahim = db_session.execute(select(Staff).where(Staff.username == "doctor_rahim")).scalar_one()
    keep = rahim.doctor_profile_id
    oid = _order(client, db_session)
    rahim.doctor_profile_id = None
    db_session.commit()
    try:
        ids, body = _queue_ids(client, DOCTOR_HEADERS)
        assert ids == set() and body["my_doctor"] is None
        assert client.post(f"{BASE}/{oid}/approve", headers=DOCTOR_HEADERS, json={}).status_code == 403
    finally:
        rahim.doctor_profile_id = keep
        db_session.commit()


# ---------------------------------------------------------------- audit viewer + user link
def test_audit_log_viewer_shows_the_two_approval_actions(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session)
    client.post(f"{BASE}/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": True})
    meta = client.get("/audit-logs/meta", headers=OWNER_HEADERS).json()
    assert "DOCTOR_APPROVAL_RECORDED_BY_STAFF" in meta["actions"]
    page = client.get("/audit-logs", headers=OWNER_HEADERS, params={"action": "DOCTOR_APPROVAL_RECORDED_BY_STAFF", "entity_type": "TEST_ORDER"}).json()
    row = next(r for r in page["items"] if r["entity_id"] == str(oid))
    assert row["acting_role"] == "ADMIN" and "on behalf of" in row["after_value"]


def test_user_admin_links_a_doctor_profile_only_to_a_doctor_user(client, db_session):
    doc = _doctor(client)
    uname = f"doc_{uuid4().hex[:6]}"
    base = {"username": uname, "display_name": "Dr Linked", "password": "Str0ng!Passw0rd#26", "role": "DOCTOR", "doctor_profile_id": doc}
    r = client.post("/users", headers=OWNER_HEADERS, json=base)
    assert r.status_code in (200, 201), r.text
    assert r.json()["doctor_profile_id"] == doc and r.json()["doctor_profile_name"]
    uid = r.json()["id"]
    bad = client.post("/users", headers=OWNER_HEADERS, json={**base, "username": f"rc_{uuid4().hex[:6]}", "role": "RECEPTIONIST"})
    assert bad.status_code == 400
    ch = client.patch(f"/users/{uid}", headers=OWNER_HEADERS, json={"doctor_profile_id": None})
    assert ch.status_code == 200, ch.text
    assert ch.json()["doctor_profile_id"] is None

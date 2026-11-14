"""Prompt 19 - editing a doctor / 3rd party in place (PATCH /referrers/{id}). Runs only against medscope_test."""
from sqlalchemy import select

from backend.app.models.audit import AuditLog
from backend.app.models.referrer import Referrer
from tests.conftest import ADMIN_HEADERS, CASHIER_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS
from tests.test_prompt15_doctor_signoff import _approval, _doctor, _order


def test_edit_updates_the_same_record_in_place(client, db_session):
    rid = _doctor(client, reg="BMDC-OLD-1")
    res = client.patch(f"/referrers/{rid}", headers=ADMIN_HEADERS, json={"phone": "01700000001", "registration_no": "BMDC-NEW-9", "specialty": "Cardiology"})
    assert res.status_code == 200, res.text
    assert res.json()["id"] == rid and res.json()["registration_no"] == "BMDC-NEW-9"
    db_session.expire_all()
    r = db_session.get(Referrer, rid)
    assert (r.phone, r.registration_no, r.specialty) == ("01700000001", "BMDC-NEW-9", "Cardiology")
    assert r.commission_type and "commission" not in res.json()  # commission is neither edited nor exposed
    row = db_session.execute(select(AuditLog).where(AuditLog.action == "UPDATE_REFERRER", AuditLog.entity_id == str(rid))).scalars().first()
    assert row is not None and "BMDC-OLD-1" in row.before_value and "BMDC-NEW-9" in row.after_value
    # a field left out is untouched; an empty name or type is refused; Owner may edit too
    assert client.patch(f"/referrers/{rid}", headers=OWNER_HEADERS, json={"name": " "}).status_code in (400, 422)
    assert client.patch(f"/referrers/{rid}", headers=OWNER_HEADERS, json={"referrer_type": "Third Party"}).json()["phone"] == "01700000001"
    assert client.patch("/referrers/99999999", headers=ADMIN_HEADERS, json={"phone": "1"}).status_code == 404


def test_edit_needs_the_same_permission_as_delete(client):
    rid = _doctor(client)
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.patch(f"/referrers/{rid}", headers=h, json={"phone": "1"}).status_code == 403
        assert client.post(f"/referrers/{rid}/delete", headers=h, json={"reason": "x"}).status_code == 403
    assert client.post(f"/referrers/{rid}/delete", headers=ADMIN_HEADERS, json={"reason": "x"}).status_code == 200
    assert client.patch(f"/referrers/{rid}", headers=ADMIN_HEADERS, json={"phone": "1"}).status_code == 409  # deleted: restore first
    assert client.post(f"/referrers/{rid}/restore", headers=ADMIN_HEADERS).status_code == 200
    assert client.patch(f"/referrers/{rid}", headers=ADMIN_HEADERS, json={"phone": "2"}).status_code == 200


def test_saved_doctor_approval_keeps_its_snapshot_after_an_edit(client, db_session):
    doc = _doctor(client, reg="BMDC-SNAP-1")
    oid = _order(client, db_session, "DOCTOR_REQUIRED")
    assert client.post(f"/doctor-approvals/{oid}/approve", headers=ADMIN_HEADERS, json={"doctor_id": doc, "attestation": True}).status_code == 201
    before = _approval(db_session, oid)
    name_before, reg_before = before.doctor_name, before.doctor_registration_no
    assert client.patch(f"/referrers/{doc}", headers=ADMIN_HEADERS, json={"name": "Dr Renamed After", "registration_no": "BMDC-CHANGED-2"}).status_code == 200
    db_session.expire_all()
    after = _approval(db_session, oid)
    assert (after.doctor_name, after.doctor_registration_no) == (name_before, reg_before) == (name_before, "BMDC-SNAP-1")

"""
Prompt 16 (Module 14) - Draft to Final report.

Covers: explicit Finalize for technician-final tests, automatic finalization with the doctor approval
(doctor-required and both-signature), the culture FINAL wait, blocked states, immutability of the stored
report (ORM guard, database trigger, API), the edit-conflict check, the Issued list / snapshot, the
placeholder notification row (no SMS) and the Ready -> Issued move. Runs only against medscope_test.
"""
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.app.models.audit import AuditLog
from backend.app.models.report import NotificationLog, ReportVersion
from backend.app.models.result import Result
from backend.app.models.test_order import TestOrder
from tests.conftest import ADMIN_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS
from tests.test_prompt15_doctor_signoff import _doctor, _order

TEC = dict(performing_role="LAB_TECH", requires_doctor=False)


def _tech_order(client, db, **kw):
    return _order(client, db, "TECHNICIAN_FINAL", **{**TEC, **kw})


def _final(db, oid):
    db.expire_all()
    return db.execute(select(ReportVersion).where(ReportVersion.test_order_id == oid)).scalar_one_or_none()


def _fin(client, oid, headers=ADMIN_HEADERS):
    return client.post(f"/worklist/{oid}/finalize-report", headers=headers)


def _approve(client, oid, doc, headers=ADMIN_HEADERS):
    return client.post(f"/doctor-approvals/{oid}/approve", headers=headers, json={"doctor_id": doc, "attestation": True})


# ---------------------------------------------------------------- COMPLETED is not "Final"
def test_submitted_technician_final_result_is_completed_but_not_final(client, db_session):
    oid = _tech_order(client, db_session)
    order = db_session.get(TestOrder, oid)
    assert order.status == "COMPLETED" and order.result.status == "ENTERED"
    assert _final(db_session, oid) is None  # COMPLETED / ENTERED never created a report
    ready = client.get("/reports/ready", headers=RECEPTIONIST_HEADERS).json()
    row = next(r for r in ready if r["test_order_id"] == oid)
    assert row["can_finalize"] is True and row["approval_rule"] == "TECHNICIAN_FINAL"


# ---------------------------------------------------------------- technician-final
def test_technician_final_explicit_finalize_creates_final_report(client, db_session):
    oid = _tech_order(client, db_session)
    r = _fin(client, oid)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "FINAL_AUTHORIZED" and body["version"] == 1 and body["report_no"].startswith("RPT-")
    rv = _final(db_session, oid)
    assert rv.id == body["report_version_id"] and rv.approval_rule == "TECHNICIAN_FINAL" and rv.doctor_approval_id is None
    assert rv.result_id == db_session.get(TestOrder, oid).result.id
    snap = rv.content_snapshot
    assert snap["findings"] == "Normal study." and snap["is_draft"] is False
    assert rv.signatures["technician"]["name"] and rv.signatures["doctor"] is None
    # audit + placeholder notification
    assert db_session.execute(select(AuditLog).where(AuditLog.action == "REPORT_FINALIZED", AuditLog.entity_id == str(rv.id))).scalar_one()
    note = db_session.execute(select(NotificationLog).where(NotificationLog.report_version_id == rv.id)).scalar_one()
    assert note.kind == "REPORT_READY_SMS" and note.status == "PENDING_INTEGRATION"
    # no second Final report
    assert _fin(client, oid).status_code == 409


def test_final_report_leaves_ready_and_shows_in_issued_list_and_snapshot(client, db_session):
    oid = _tech_order(client, db_session)
    rid = _fin(client, oid).json()["report_version_id"]
    assert oid not in {r["test_order_id"] for r in client.get("/reports/ready", headers=RECEPTIONIST_HEADERS).json()}
    issued = client.get("/reports", headers=RECEPTIONIST_HEADERS, params={"limit": 100}).json()
    item = next(i for i in issued if i["report_version_id"] == rid)
    assert item["has_snapshot"] is True and item["version"] == 1
    s = client.get(f"/reports/{rid}/snapshot", headers=RECEPTIONIST_HEADERS)
    assert s.status_code == 200
    j = s.json()
    assert j["report_status"] == "FINAL" and j["findings"] == "Normal study." and j["signatures"]["technician"]["name"]
    assert "price" not in str(j).lower() and "due" not in j
    pv = client.get(f"/worklist/{oid}/result-preview", headers=ADMIN_HEADERS).json()
    assert pv["report_status"] == "FINAL" and pv["can_finalize"] is False


def test_finalize_permissions_and_missing_order(client, db_session):
    oid = _tech_order(client, db_session)
    assert _fin(client, oid, RECEPTIONIST_HEADERS).status_code == 403
    assert _final(db_session, oid) is None
    assert _fin(client, 99999999).status_code == 404
    assert client.get("/reports/99999999/snapshot", headers=RECEPTIONIST_HEADERS).status_code == 404


def test_draft_result_cannot_be_finalized(client, db_session):
    oid = _tech_order(client, db_session, result="DRAFT")
    r = _fin(client, oid)
    assert r.status_code == 409 and "draft" in r.json()["detail"].lower()
    assert _final(db_session, oid) is None
    assert _fin(client, _tech_order(client, db_session, result=None)).status_code == 409


@pytest.mark.parametrize("how", ["REJECTED", "CANCELLED", "SPOILED", "NOT_PERFORMED"])
def test_dead_orders_are_never_finalizable(client, db_session, how):
    oid = _tech_order(client, db_session)
    order = db_session.get(TestOrder, oid)
    if how == "NOT_PERFORMED":
        order.outcome = "NOT_PERFORMED"
    else:
        order.status = how
    db_session.commit()
    assert _fin(client, oid).status_code == 409
    assert _final(db_session, oid) is None


# ---------------------------------------------------------------- doctor-required / both-signature
def test_doctor_required_finalizes_automatically_with_the_approval(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "DOCTOR_REQUIRED")
    assert _final(db_session, oid) is None
    assert _fin(client, oid).status_code in (409, 403)  # no approval yet (or not in the actor's queue)
    assert _approve(client, oid, doc).status_code == 201
    rv = _final(db_session, oid)
    assert rv is not None and rv.approval_rule == "DOCTOR_REQUIRED"
    assert rv.doctor_approval_id and rv.signatures["doctor"]["registration_no"] == "BMDC-A-12345"
    assert rv.signatures["doctor"]["is_attestation"] is True
    assert db_session.get(TestOrder, oid).status == "COMPLETED"
    # the audit rows of the approval and the finalization are both there
    acts = {a for (a,) in db_session.execute(select(AuditLog.action).where(AuditLog.entity_id.in_([str(oid), str(rv.id)]))).all()}
    assert {"DOCTOR_APPROVAL_RECORDED_BY_STAFF", "REPORT_FINALIZED"} <= acts


def test_both_signature_needs_both_and_finalizes_with_the_second(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "BOTH_SIGNATURES")
    b = _fin(client, oid)
    assert b.status_code == 409 and "doctor" in b.json()["detail"].lower()  # technician signed, doctor missing
    assert _final(db_session, oid) is None
    pv = client.get(f"/worklist/{oid}/result-preview", headers=ADMIN_HEADERS).json()
    assert pv["can_finalize"] is False and pv["doctor_approved"] is False
    assert _approve(client, oid, doc).status_code == 201
    rv = _final(db_session, oid)
    assert rv.signatures["technician"]["name"] and rv.signatures["doctor"]["name"]


def test_doctor_login_approval_also_finalizes(client, db_session):
    from tests.conftest import DOCTOR_HEADERS
    from tests.test_prompt15_doctor_signoff import _my_profile_id
    mine = _my_profile_id(db_session)
    oid = _order(client, db_session, "DOCTOR_REQUIRED")
    client.post(f"/doctor-approvals/{oid}/assign-doctor", headers=ADMIN_HEADERS, json={"doctor_id": mine})
    assert client.post(f"/doctor-approvals/{oid}/approve", headers=DOCTOR_HEADERS, json={}).status_code == 201
    rv = _final(db_session, oid)
    assert rv.signatures["doctor"]["is_attestation"] is False and rv.issued_by_id != None  # noqa: E711


# ---------------------------------------------------------------- culture
def test_technician_final_culture_waits_for_stage_final(client, db_session):
    oid = _tech_order(client, db_session, report_template="CULTURE_SENSITIVITY")
    assert db_session.get(TestOrder, oid).status == "IN_PROGRESS"
    b = _fin(client, oid)
    assert b.status_code == 409 and "culture" in b.json()["detail"].lower()
    for stage in ("INCUBATING", "PRELIMINARY"):
        assert client.post(f"/worklist/{oid}/culture-stage", headers=ADMIN_HEADERS, json={"stage": stage}).status_code == 200
        assert _fin(client, oid).status_code == 409
    assert client.post(f"/worklist/{oid}/culture-stage", headers=ADMIN_HEADERS, json={"stage": "FINAL"}).status_code == 200
    assert _final(db_session, oid) is None  # stage FINAL is not the report being Final
    assert _fin(client, oid).status_code == 201
    assert db_session.get(TestOrder, oid).status == "COMPLETED"


def test_culture_with_doctor_approval_finalizes_when_stage_reaches_final(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "BOTH_SIGNATURES", report_template="CULTURE_SENSITIVITY")
    assert client.post(f"/worklist/{oid}/culture-stage", headers=ADMIN_HEADERS, json={"stage": "PRELIMINARY"}).status_code == 200
    assert _approve(client, oid, doc).status_code == 201
    assert _final(db_session, oid) is None  # approved, but the culture is not FINAL yet
    assert client.post(f"/worklist/{oid}/culture-stage", headers=ADMIN_HEADERS, json={"stage": "FINAL"}).status_code == 200
    rv = _final(db_session, oid)
    assert rv is not None and rv.signatures["doctor"]["name"]
    assert db_session.get(TestOrder, oid).status == "COMPLETED"


# ---------------------------------------------------------------- immutability / non-destructiveness
def test_final_report_content_cannot_be_altered_by_later_changes(client, db_session):
    oid = _tech_order(client, db_session)
    rid = _fin(client, oid).json()["report_version_id"]
    before = client.get(f"/reports/{rid}/snapshot", headers=RECEPTIONIST_HEADERS).json()
    rv = _final(db_session, oid)
    stored_snapshot, stored_sigs, stored_no = rv.content_snapshot, rv.signatures, rv.report_no

    # 1. the underlying result changes afterwards (directly in the database)
    res = db_session.execute(select(Result).where(Result.test_order_id == oid)).scalar_one()
    res.findings, res.impression = "CHANGED LATER", "CHANGED LATER"
    db_session.commit()
    # 2. the API refuses to change the result of a Final report
    r = client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={"status": "ENTERED", "findings": "x", "impression": "y"})
    assert r.status_code == 409
    # 3. the stored report is untouched
    after = client.get(f"/reports/{rid}/snapshot", headers=RECEPTIONIST_HEADERS).json()
    assert after == before and after["findings"] == "Normal study."
    rv = _final(db_session, oid)
    assert (rv.content_snapshot, rv.signatures, rv.report_no) == (stored_snapshot, stored_sigs, stored_no)

    # 4. the ORM guard refuses an in-app change of stored content ...
    rv.content_snapshot = {"findings": "tampered"}
    with pytest.raises(ValueError):
        db_session.flush()
    db_session.rollback()
    rv = _final(db_session, oid)
    rv.findings_summary = "tampered"
    with pytest.raises(ValueError):
        db_session.flush()
    db_session.rollback()
    # 5. ... and the database trigger refuses it for any other writer too
    for col, val in (("findings_summary", "'tampered'"), ("content_snapshot", "'{\"a\": 1}'::json"), ("report_no", "'X'"), ("issued_by_id", "NULL")):
        with pytest.raises(DBAPIError):
            db_session.execute(text(f"UPDATE report_versions SET {col} = {val} WHERE id = :i"), {"i": rid})
        db_session.rollback()
    # a status change (Module 15 will need it) is not content and stays possible
    db_session.execute(text("UPDATE report_versions SET authorized = authorized WHERE id = :i"), {"i": rid})
    db_session.rollback()
    assert _final(db_session, oid).content_snapshot == stored_snapshot


def test_stored_range_snapshot_survives_a_range_change(client, db_session):
    """Same style as Prompt 14: the Final report keeps the reference range text it was finalized with."""
    from tests.test_prompt14_reference_ranges import HB_BANDS, _make_test, _order as _o14, _save, _template
    tid, code, comps = _make_test(db_session, {"HB": HB_BANDS})
    oid = _o14(client, db_session, tid, 30, "years", "Male")
    comp_map = {k: c["id"] for k, c in _template(client, oid).items()}
    _save(client, oid, comp_map, {"HB": "14.0"})
    rid = _fin(client, oid).json()["report_version_id"]
    snap = client.get(f"/reports/{rid}/snapshot", headers=RECEPTIONIST_HEADERS).json()
    item = next(i for i in snap["items"] if i["component_code"] == "HB")
    assert item["reference_range"] == "13.0 - 17.0 g/dL" and item["value"] == "14.0"
    # a new version of the male band afterwards
    from backend.app.models.test import ReferenceRangeVersion
    band = db_session.execute(select(ReferenceRangeVersion).where(
        ReferenceRangeVersion.test_component_id == comps["HB"], ReferenceRangeVersion.sex == "MALE", ReferenceRangeVersion.is_current == True)).scalar_one()  # noqa: E712
    r = client.post(f"/reference-ranges/versions/{band.id}/new-version", headers=OWNER_HEADERS, json={
        "sex": "MALE", "age_days_min": band.age_days_min, "ref_min": 10.0, "ref_max": 12.0, "critical_min": 5.0, "critical_max": 20.0,
        "reference_range_text": "10.0 - 12.0 g/dL", "note": "changed"})
    assert r.status_code in (200, 201), r.text
    again = client.get(f"/reports/{rid}/snapshot", headers=RECEPTIONIST_HEADERS).json()
    assert again == snap


def test_one_final_report_per_order_is_enforced_by_the_database(client, db_session):
    oid = _tech_order(client, db_session)
    _fin(client, oid)
    rv = _final(db_session, oid)
    db_session.add(ReportVersion(tenant_id=rv.tenant_id, test_order_id=oid, report_no="RPT-DUP", version=2, status="FINAL_AUTHORIZED"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------- result lock after approval, edit conflict
def test_result_is_locked_once_a_doctor_approval_is_recorded(client, db_session):
    doc = _doctor(client)
    oid = _order(client, db_session, "BOTH_SIGNATURES", report_template="CULTURE_SENSITIVITY")  # approval without a Final report yet
    assert _approve(client, oid, doc).status_code == 201
    assert _final(db_session, oid) is None
    r = client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={"status": "ENTERED", "findings": "x"})
    assert r.status_code == 409 and "approval" in r.json()["detail"].lower()


def test_edit_conflict_is_detected_on_save(client, db_session):
    oid = _tech_order(client, db_session, result="DRAFT")
    t = client.get(f"/worklist/{oid}/result-template", headers=ADMIN_HEADERS).json()
    stamp = t["existing_result"]["updated_at"]
    assert t["existing_result"]["updated_by_name"]
    # someone else saves in the meantime
    other = client.post(f"/worklist/{oid}/result", headers=OWNER_HEADERS, json={"status": "DRAFT", "findings": "Owner edit"})
    assert other.status_code == 200, other.text
    # the first editor still holds the old stamp
    stale = client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={"status": "DRAFT", "findings": "mine", "expected_updated_at": stamp})
    assert stale.status_code == 409 and "changed by" in stale.json()["detail"]
    fresh_stamp = client.get(f"/worklist/{oid}/result-template", headers=ADMIN_HEADERS).json()["existing_result"]["updated_at"]
    ok = client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={"status": "DRAFT", "findings": "mine", "expected_updated_at": fresh_stamp})
    assert ok.status_code == 200
    # without the stamp the old behaviour is unchanged (API compatibility)
    assert client.post(f"/worklist/{oid}/result", headers=ADMIN_HEADERS, json={"status": "DRAFT", "findings": "again"}).status_code == 200


# ---------------------------------------------------------------- no SMS anywhere
def test_only_placeholder_notification_rows_exist(client, db_session):
    oid = _tech_order(client, db_session)
    _fin(client, oid)
    statuses = {s for (s,) in db_session.execute(select(NotificationLog.status)).all()}
    assert statuses == {"PENDING_INTEGRATION"}
    cols = {c.name for c in NotificationLog.__table__.columns}
    assert "phone" not in cols and "message" not in cols  # nothing that could be sent

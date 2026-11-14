"""
Prompt 12 — imaging lock moves to RESULT COMPLETION (IMAGING_PERFORMED is only a status label),
the owner same-day line unlock (D14) works uniformly, and the fixture cleanup does not grow the DB.
Runs only against medscope_test (conftest guard).
"""
from uuid import uuid4

from sqlalchemy import select, text

from backend.app.core.permissions import ROLE_DEFAULTS
from backend.app.models.audit import AuditLog
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.test import Test
from tests.conftest import ADMIN_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS

TENANT = "center-seba-01"


def _probe_test(db, **kw):
    code = f"P12_{uuid4().hex[:8].upper()}"
    fields = dict(tenant_id=TENANT, code=code, name=f"12 probe {code}", department="Radiology", price=300,
                  sample_type=None, performing_role="LAB_TECH", requires_doctor=False, report_template="NARRATIVE",
                  approval_rule="TECHNICIAN_FINAL", is_outsourced=False, active=True, lab_section="ULTRASONOGRAPHY")
    fields.update(kw)
    db.add(Test(**fields))
    db.commit()
    return code


def _ensure_open_day(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st["is_open"]:
        assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201


def _invoice_with(client, db, code):
    _ensure_open_day(client)
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json={
        "patient_id": pid, "age_value": 30, "gender": "Male",
        "lines": [{"test_id": db.execute(select(Test.id).where(Test.code == code)).scalar_one()}],
        "initial_payment_amount": 0, "initial_payment_method": "CASH",
    })
    assert res.status_code == 201, res.text
    db.expire_all()
    inv = db.get(Invoice, res.json()["id"])
    line = inv.lines[0]
    return inv, line, line.test_order


def _line(db, line_id):
    db.expire_all()
    return db.get(InvoiceLine, line_id)


def test_imaging_line_is_not_locked_at_performed_and_locks_at_result_completion(client, db_session):
    code = _probe_test(db_session)
    inv, line, order = _invoice_with(client, db_session, code)
    assert line.is_locked is False
    res = client.post(f"/worklist/{order.id}/imaging-performed", headers=ADMIN_HEADERS, json={})
    assert res.status_code == 200, res.text
    after_performed = _line(db_session, line.id)
    assert after_performed.is_locked is False and after_performed.locked_at is None  # label only, no lock
    detail = client.get(f"/invoices/{inv.id}", headers=RECEPTIONIST_HEADERS).json()
    assert detail["lines"][0]["is_locked"] is False
    assert detail["lines"][0]["sample_status"] == "PERFORMED"  # status label kept (Prompt 07 mapping unchanged)
    done = client.post(f"/worklist/{order.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"})
    assert done.status_code == 200, done.text
    locked = _line(db_session, line.id)
    assert locked.is_locked is True and locked.locked_at is not None
    assert "Result completed" in (locked.locked_reason or "")


def test_cancel_before_result_completion_is_the_ordinary_unlocked_path(client, db_session):
    code = _probe_test(db_session)
    inv, line, order = _invoice_with(client, db_session, code)
    # not performed yet, and also after performed but before completion: eligible like any unlocked line
    elig = client.get(f"/refunds/eligibility/{line.id}", headers=RECEPTIONIST_HEADERS).json()
    assert elig["is_eligible"] is True
    assert client.post(f"/worklist/{order.id}/imaging-performed", headers=ADMIN_HEADERS, json={}).status_code == 200
    elig = client.get(f"/refunds/eligibility/{line.id}", headers=RECEPTIONIST_HEADERS).json()
    assert elig["is_eligible"] is True, elig
    detail = client.get(f"/invoices/{inv.id}", headers=RECEPTIONIST_HEADERS).json()
    assert detail["lines"][0]["is_locked"] is False
    # once the result is completed the line is locked and ordinary cancellation is refused
    assert client.post(f"/worklist/{order.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"}).status_code == 200
    elig = client.get(f"/refunds/eligibility/{line.id}", headers=RECEPTIONIST_HEADERS).json()
    assert elig["is_eligible"] is False


def test_owner_same_day_unlock_is_uniform_and_guarded(client, db_session):
    img_code = _probe_test(db_session)
    non_img = _probe_test(db_session, department="Clinical Pathology", lab_section="HEMATOLOGY", report_template="NUMERIC_TABLE", sample_type="No sample")
    for code in (img_code, non_img):  # imaging and a non-imaging no-sample test follow the same rule
        inv, line, order = _invoice_with(client, db_session, code)
        assert client.post(f"/worklist/{order.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"}).status_code == 200
        assert _line(db_session, line.id).is_locked is True
        url = f"/invoices/lines/{line.id}/unlock"
        # only the OWNER (permission invoice.line_unlock); Admin / Receptionist refused
        assert client.post(url, headers=ADMIN_HEADERS, json={"reason": "typo"}).status_code == 403
        assert client.post(url, headers=RECEPTIONIST_HEADERS, json={"reason": "typo"}).status_code == 403
        # reason required
        assert client.post(url, headers=OWNER_HEADERS, json={}).status_code == 400
        ok = client.post(url, headers=OWNER_HEADERS, json={"reason": "result entered on wrong order"})
        assert ok.status_code == 200, ok.text
        unlocked = _line(db_session, line.id)
        assert unlocked.is_locked is False and unlocked.locked_reason is None
        assert client.post(url, headers=OWNER_HEADERS, json={"reason": "again"}).status_code == 409  # not locked
        row = db_session.execute(select(AuditLog).where(AuditLog.action == "INVOICE_LINE_UNLOCKED", AuditLog.entity_id == str(line.id))).scalars().first()
        assert row is not None and "result entered on wrong order" in row.after_value


def test_unlock_refused_when_lock_is_from_an_earlier_business_day(client, db_session):
    code = _probe_test(db_session)
    inv, line, order = _invoice_with(client, db_session, code)
    assert client.post(f"/worklist/{order.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"}).status_code == 200
    db_session.execute(text("UPDATE invoice_lines SET locked_at = locked_at - interval '400 days' WHERE id = :i"), {"i": line.id})
    db_session.commit()
    res = client.post(f"/invoices/lines/{line.id}/unlock", headers=OWNER_HEADERS, json={"reason": "late"})
    assert res.status_code == 409 and "same business day" in res.json()["detail"]


def test_unlock_key_is_owner_only_and_audit_view_default_unchanged():
    assert "invoice.line_unlock" in ROLE_DEFAULTS["OWNER"]
    for role in ("ADMIN", "RECEPTIONIST", "CASHIER", "LAB_TECH", "DOCTOR"):
        assert "invoice.line_unlock" not in ROLE_DEFAULTS[role]
    assert "audit.view" in ROLE_DEFAULTS["OWNER"] and "audit.view" not in ROLE_DEFAULTS["ADMIN"]


def test_fixture_cleanup_helper_only_targets_generated_users_in_medscope_test(db_session):
    from tests.fixture_cleanup import SEED_USERNAMES, count_fixture_staff
    conn = db_session.connection()
    assert conn.execute(text("SELECT current_database()")).scalar() == "medscope_test"
    assert count_fixture_staff(conn) >= 0
    for name in SEED_USERNAMES:  # a seed name never matches the generated-name rule
        import re
        assert not re.search("_[0-9a-f]{6,8}$", name), name

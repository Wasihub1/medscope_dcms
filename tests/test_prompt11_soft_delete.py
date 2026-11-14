"""
Prompt 11 - soft delete (User, Doctor/3rd party, Catalog Test), Draft Invoice discard (hard delete),
and the read-only Audit Log viewer. Runs only against medscope_test (conftest guard).
"""
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.core.permissions import (
    MONEY_PERMISSIONS,
    PERMISSIONS,
    ROLE_DEFAULTS,
    effective_permissions,
)
from backend.app.models.audit import AuditLog
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.payment import Payment
from backend.app.models.patient import Patient
from backend.app.models.referrer import Referrer
from backend.app.models.result import Result
from backend.app.models.test import Test
from backend.app.models.test_order import TestOrder
from backend.app.models.user import Staff
from backend.app.models.visit import Visit
from tests.conftest import (
    ADMIN_HEADERS,
    CASHIER_HEADERS,
    OWNER_HEADERS,
    RECEPTIONIST_HEADERS,
    TECH_KAMAL_HEADERS,
)
from tests.test_prompt10f_owner_findings import (
    PASSWORD,
    TENANT,
    _audits,
    _client,
    _empty_usg_room,
    _invoice,
    _login,
    _new_user,
    _order,
    _save,
    _test,
    _usg_orders,
)


def _patient_id(db):
    return db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()


def _payload(db, codes, **extra):
    body = {
        "patient_id": _patient_id(db), "age_value": 30, "gender": "Male",
        "lines": [{"test_id": db.execute(select(Test.id).where(Test.code == c)).scalar_one()} for c in codes],
        "initial_payment_amount": 0, "initial_payment_method": "CASH",
    }
    body.update(extra)
    return body


def _new_referrer(client, name, type_="Doctor"):
    res = client.post("/referrers", headers=RECEPTIONIST_HEADERS, json={
        "name": f"{name} {_uniq()}", "referrer_type": type_, "phone": "01700000000", "commission_rate": 10,
    })
    assert res.status_code == 201, res.text
    return res.json()


def _uniq():
    from uuid import uuid4
    return uuid4().hex[:6]


def _delete(client, path, headers, reason="probe reason"):
    return client.post(path, headers=headers, json={"reason": reason} if reason is not None else {})


# ===========================================================================
# Permissions module
# ===========================================================================
def test_permission_keys_for_prompt11():
    assert len(PERMISSIONS) == 43 and len(MONEY_PERMISSIONS) == 24  # Prompt 12 added invoice.line_unlock (owner-only, not money)
    assert "audit.view" in ROLE_DEFAULTS["OWNER"]
    for role in ("ADMIN", "RECEPTIONIST", "CASHIER", "LAB_TECH", "DOCTOR"):
        assert "audit.view" not in ROLE_DEFAULTS[role], role
    for key in ("referrer.manage", "test_catalog.manage"):
        assert key in ROLE_DEFAULTS["OWNER"] and key in ROLE_DEFAULTS["ADMIN"]
        for role in ("RECEPTIONIST", "CASHIER", "LAB_TECH", "DOCTOR"):
            assert key not in ROLE_DEFAULTS[role], (key, role)
    # an Admin can be granted audit.view; LAB_TECH / DOCTOR never can (money key)
    assert "audit.view" in effective_permissions("ADMIN", {"audit.view": True})
    assert "audit.view" not in effective_permissions("LAB_TECH", {"audit.view": True})
    assert "audit.view" not in effective_permissions("DOCTOR", {"audit.view": True})


def test_only_the_draft_discard_is_a_real_delete_and_no_other_entity_gets_delete(client):
    from backend.app.main import app
    spec = app.openapi()
    deletes = [p for p, ops in spec["paths"].items() if "delete" in ops]
    assert deletes == ["/api/v1/invoices/{invoice_id}/draft"], deletes
    # Patient / Payment / Refund / Result / Sample / Invoice (non-draft) have no delete or deactivate path
    forbidden = ("patients", "payments", "refunds", "/results", "/samples", "business-day", "ledger", "stock")
    for path in spec["paths"]:
        if any(f in path for f in forbidden):
            assert not any(w in path for w in ("/delete", "/restore", "/deactivate", "/discard")), path


# ===========================================================================
# Catalog Test
# ===========================================================================
def test_soft_delete_test_hides_it_and_leaves_old_records_untouched(client, db_session):
    code = _test(db_session, sample_type="Blood")
    test_id = db_session.execute(select(Test.id).where(Test.code == code)).scalar_one()
    inv = _invoice(client, db_session, [code])
    order = _order(db_session, inv["id"], code)
    assert client.post(f"/worklist/{order.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, order.id, "ENTERED").status_code == 200
    db_session.expire_all()
    line = db_session.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv["id"])).scalar_one()
    before = (line.test_id, line.test_code_snapshot, line.test_name_snapshot, line.unit_price_snapshot, line.net_price, line.status)
    res_before = db_session.execute(select(Result.status).where(Result.test_order_id == order.id)).scalar_one()

    # reason is mandatory; permission is mandatory
    assert _delete(client, f"/tests/{test_id}/delete", ADMIN_HEADERS, None).status_code == 400
    assert _delete(client, f"/tests/{test_id}/delete", ADMIN_HEADERS, "   ").status_code == 400
    assert _delete(client, f"/tests/{test_id}/delete", ADMIN_HEADERS, "x" * 501).status_code == 400
    assert _delete(client, f"/tests/{test_id}/delete", RECEPTIONIST_HEADERS).status_code == 403
    assert _delete(client, f"/tests/{test_id}/delete", TECH_KAMAL_HEADERS).status_code == 403
    res = _delete(client, f"/tests/{test_id}/delete", ADMIN_HEADERS, "Retired from the price list")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["delete_reason"] == "Retired from the price list" and body["deleted_by_name"]
    assert _delete(client, f"/tests/{test_id}/delete", ADMIN_HEADERS).status_code == 409  # already deleted

    # hidden from every new-selection surface
    assert code not in {t["code"] for t in client.get("/tests", headers=RECEPTIONIST_HEADERS, params={"q": code}).json()}
    found = client.get("/search", headers=RECEPTIONIST_HEADERS, params={"q": code}).json()
    assert all(code not in t["title"] for t in found["tests"])
    new_inv = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_payload(db_session, [code]))
    assert new_inv.status_code == 400 and "Deleted test" in new_inv.json()["detail"]
    new_draft = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=_payload(db_session, [code]))
    assert new_draft.status_code == 400

    # old invoice line, its stored price, the order and the result are exactly as before
    db_session.expire_all()
    line = db_session.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv["id"])).scalar_one()
    assert (line.test_id, line.test_code_snapshot, line.test_name_snapshot, line.unit_price_snapshot, line.net_price, line.status) == before
    assert db_session.execute(select(Result.status).where(Result.test_order_id == order.id)).scalar_one() == res_before
    assert db_session.get(TestOrder, order.id) is not None
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS)
    assert detail.status_code == 200 and detail.json()["net"] == inv["net"]
    assert order.id in {i["test_order_id"] for i in client.get("/worklist", headers=TECH_KAMAL_HEADERS, params={"limit": 200}).json()}

    # Deleted view: Admin/Owner only
    listing = client.get("/tests/deleted", headers=ADMIN_HEADERS, params={"q": code})
    assert listing.status_code == 200 and [i["id"] for i in listing.json()] == [test_id]
    assert client.get("/tests/deleted", headers=OWNER_HEADERS).status_code == 200
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.get("/tests/deleted", headers=h).status_code == 403
    audit = _audits(db_session, "TEST_SOFT_DELETED", test_id)
    assert len(audit) == 1 and "reason: Retired from the price list" in audit[0].after_value

    # restore: same permission, works, selectable again
    assert client.post(f"/tests/{test_id}/restore", headers=RECEPTIONIST_HEADERS).status_code == 403
    assert client.post(f"/tests/{test_id}/restore", headers=ADMIN_HEADERS).status_code == 200
    assert client.post(f"/tests/{test_id}/restore", headers=ADMIN_HEADERS).status_code == 409
    assert code in {t["code"] for t in client.get("/tests", headers=RECEPTIONIST_HEADERS, params={"q": code}).json()}
    assert client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=_payload(db_session, [code])).status_code == 201
    assert len(_audits(db_session, "TEST_RESTORED", test_id)) == 1
    db_session.expire_all()
    t = db_session.get(Test, test_id)
    assert t.deleted_at is None and t.deleted_by_id is None and t.delete_reason is None


# ===========================================================================
# Doctor / 3rd party (one referrers table)
# ===========================================================================
def test_soft_delete_referrer_blocks_new_selection_and_keeps_old_bills(client, db_session):
    doctor = _new_referrer(client, "Dr Probe", "Doctor")
    clinic = _new_referrer(client, "Probe Clinic", "Clinic")
    code = _test(db_session, sample_type="Blood")
    old = client.post("/invoices", headers=RECEPTIONIST_HEADERS,
                      json=_payload(db_session, [code], prescribed_by_id=doctor["id"], referrer_id=clinic["id"]))
    assert old.status_code == 201, old.text
    old_id = old.json()["id"]
    # a draft that already carries the doctor
    draft_body = _payload(db_session, [code], prescribed_by_id=doctor["id"])
    draft = client.post("/invoices/drafts", headers=RECEPTIONIST_HEADERS, json=draft_body)
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    assert _delete(client, f"/referrers/{doctor['id']}/delete", ADMIN_HEADERS, None).status_code == 400
    assert _delete(client, f"/referrers/{doctor['id']}/delete", RECEPTIONIST_HEADERS).status_code == 403
    assert _delete(client, f"/referrers/{doctor['id']}/delete", TECH_KAMAL_HEADERS).status_code == 403
    assert _delete(client, f"/referrers/{doctor['id']}/delete", ADMIN_HEADERS, "Left the area").status_code == 200
    assert _delete(client, f"/referrers/{clinic['id']}/delete", OWNER_HEADERS, "Closed").status_code == 200
    assert _delete(client, f"/referrers/{doctor['id']}/delete", ADMIN_HEADERS).status_code == 409

    # gone from the selection list
    names = {r["name"] for r in client.get("/referrers", headers=RECEPTIONIST_HEADERS, params={"limit": 500}).json()}
    assert doctor["name"] not in names and clinic["name"] not in names
    # new bills cannot pick them
    for body in (_payload(db_session, [code], prescribed_by_id=doctor["id"]), _payload(db_session, [code], referrer_id=clinic["id"])):
        r = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json=body)
        assert r.status_code == 400 and "deleted" in r.json()["detail"], r.text
    # the old bill still shows both names, with the same totals
    detail = client.get(f"/invoices/{old_id}", headers=RECEPTIONIST_HEADERS).json()
    assert detail["prescribed_by_name"] == doctor["name"] and detail["referrer_name"] == clinic["name"]
    assert detail["net"] == old.json()["net"]
    # an existing draft may keep saving with the same doctor, but Finalize treats it as new billing
    assert client.put(f"/invoices/{draft_id}/draft", headers=RECEPTIONIST_HEADERS, json=draft_body).status_code == 200
    fin = client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS)
    assert fin.status_code == 400 and "deleted" in fin.json()["detail"]

    # Deleted view with type filter, Admin/Owner only
    rows = client.get("/referrers/deleted", headers=ADMIN_HEADERS, params={"type": "Clinic"}).json()
    assert clinic["id"] in {r["id"] for r in rows} and doctor["id"] not in {r["id"] for r in rows}
    row = next(r for r in client.get("/referrers/deleted", headers=ADMIN_HEADERS).json() if r["id"] == doctor["id"])
    assert row["delete_reason"] == "Left the area" and row["deleted_by_name"]
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.get("/referrers/deleted", headers=h).status_code == 403

    # restore
    assert client.post(f"/referrers/{doctor['id']}/restore", headers=RECEPTIONIST_HEADERS).status_code == 403
    assert client.post(f"/referrers/{doctor['id']}/restore", headers=ADMIN_HEADERS).status_code == 200
    assert client.post(f"/referrers/{clinic['id']}/restore", headers=OWNER_HEADERS).status_code == 200
    assert doctor["name"] in {r["name"] for r in client.get("/referrers", headers=RECEPTIONIST_HEADERS, params={"limit": 500}).json()}
    fin = client.post(f"/invoices/{draft_id}/finalize", headers=RECEPTIONIST_HEADERS)
    assert fin.status_code in (200, 201), fin.text
    assert len(_audits(db_session, "REFERRER_SOFT_DELETED", doctor["id"])) == 1
    assert len(_audits(db_session, "REFERRER_RESTORED", doctor["id"])) == 1


# ===========================================================================
# User
# ===========================================================================
def test_user_delete_rules_login_gate_and_restore(client, db_session):
    victim = _new_user("RECEPTIONIST")
    vclient = _login(victim["username"])
    assert vclient.get("/auth/me").status_code == 200

    assert _delete(client, f"/users/{victim['id']}/delete", ADMIN_HEADERS, None).status_code == 400
    assert _delete(client, f"/users/{victim['id']}/delete", RECEPTIONIST_HEADERS).status_code == 403
    assert _delete(client, f"/users/{victim['id']}/delete", TECH_KAMAL_HEADERS).status_code == 403
    res = _delete(client, f"/users/{victim['id']}/delete", ADMIN_HEADERS, "Left the center")
    assert res.status_code == 200, res.text
    assert res.json()["active"] is False
    assert _delete(client, f"/users/{victim['id']}/delete", ADMIN_HEADERS).status_code == 409

    # existing session is revoked; login is refused
    assert vclient.get("/auth/me").status_code == 401
    assert _client().post("/auth/login", json={"username": victim["username"], "password": PASSWORD}).status_code == 401
    # hidden from the normal list, listed in the Deleted view
    assert victim["id"] not in {u["id"] for u in client.get("/users", headers=ADMIN_HEADERS).json()}
    deleted = client.get("/users/deleted", headers=ADMIN_HEADERS).json()
    row = next(r for r in deleted if r["id"] == victim["id"])
    assert row["delete_reason"] == "Left the center" and row["deleted_by_name"]
    for h in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.get("/users/deleted", headers=h).status_code == 403

    # a deleted user is blocked even if the active flag is switched back on (both flags are checked)
    staff = db_session.get(Staff, victim["id"])
    db_session.refresh(staff)
    staff.active = True
    db_session.commit()
    assert _client().post("/auth/login", json={"username": victim["username"], "password": PASSWORD}).status_code == 401
    staff.active = False
    db_session.commit()

    # reactivate is refused while deleted; restore keeps the user inactive; reactivate then works
    assert client.post(f"/users/{victim['id']}/reactivate", headers=ADMIN_HEADERS).status_code == 409
    assert client.post(f"/users/{victim['id']}/restore", headers=RECEPTIONIST_HEADERS).status_code == 403
    restored = client.post(f"/users/{victim['id']}/restore", headers=ADMIN_HEADERS)
    assert restored.status_code == 200 and restored.json()["active"] is False
    assert client.post(f"/users/{victim['id']}/restore", headers=ADMIN_HEADERS).status_code == 409
    assert _client().post("/auth/login", json={"username": victim["username"], "password": PASSWORD}).status_code == 401
    assert client.post(f"/users/{victim['id']}/reactivate", headers=ADMIN_HEADERS).status_code == 200
    assert _client().post("/auth/login", json={"username": victim["username"], "password": PASSWORD}).status_code == 200
    assert victim["id"] in {u["id"] for u in client.get("/users", headers=ADMIN_HEADERS).json()}
    assert len(_audits(db_session, "USER_SOFT_DELETED", victim["id"])) == 1
    assert len(_audits(db_session, "USER_RESTORED", victim["id"])) == 1


def test_user_delete_refuses_self_last_admin_and_owner_escalation(client, db_session):
    admin2 = _new_user("ADMIN")
    aclient = _login(admin2["username"])
    # self-delete refused
    assert aclient.post(f"/users/{admin2['id']}/delete", json={"reason": "me"}).status_code == 403
    # last active user-manager protected (same helper as deactivate)
    target = _new_user("ADMIN")
    with patch("backend.app.services.user_admin_service._count_active_user_admins", return_value=0):
        res = _delete(client, f"/users/{target['id']}/delete", ADMIN_HEADERS, "probe")
    assert res.status_code == 409 and "last active" in res.json()["detail"]
    db_session.expire_all()
    assert db_session.get(Staff, target["id"]).deleted_at is None
    # only an Owner may delete an Owner account
    owner2 = _new_user("OWNER", creator=OWNER_HEADERS)
    assert _delete(client, f"/users/{owner2['id']}/delete", ADMIN_HEADERS, "probe").status_code == 403
    assert _delete(client, f"/users/{owner2['id']}/delete", OWNER_HEADERS, "probe").status_code == 200


def test_deleting_a_technician_empties_the_room_like_deactivate(client, db_session):
    _empty_usg_room(db_session)
    tech = _new_user("LAB_TECH", lab_section="ULTRASONOGRAPHY")
    _, (o,) = _usg_orders(client, db_session, 1)
    assert o.status == "ASSIGNED"
    res = _delete(client, f"/users/{tech['id']}/delete", ADMIN_HEADERS, "Resigned")
    assert res.status_code == 200, res.text
    db_session.expire_all()
    assert db_session.get(TestOrder, o.id).status == "UNASSIGNED"
    assert db_session.get(TestOrder, o.id).lab_section == "ULTRASONOGRAPHY"
    assert len(_audits(db_session, "ORDER_UNASSIGNED_ROOM_EMPTY", o.id)) == 1
    assert len(_audits(db_session, "USER_SOFT_DELETED", tech["id"])) == 1
    # past audit rows about the deleted user are untouched
    assert _audits(db_session, "USER_CREATED", tech["id"])
    # restore + reactivate runs the normal release-on-join
    assert client.post(f"/users/{tech['id']}/restore", headers=ADMIN_HEADERS).status_code == 200
    db_session.expire_all()
    assert db_session.get(TestOrder, o.id).status == "UNASSIGNED"  # restore itself moves nothing
    assert client.post(f"/users/{tech['id']}/reactivate", headers=ADMIN_HEADERS).status_code == 200
    db_session.expire_all()
    assert db_session.get(TestOrder, o.id).status == "ASSIGNED"


# ===========================================================================
# Draft discard (hard delete)
# ===========================================================================
def _make_draft(client, db, headers=RECEPTIONIST_HEADERS):
    code = _test(db, sample_type="Blood")
    res = client.post("/invoices/drafts", headers=headers, json=_payload(db, [code]))
    assert res.status_code == 201, res.text
    return res.json()


def _counts(db, invoice_id):
    return {
        "invoices": db.execute(select(func.count(Invoice.id)).where(Invoice.id == invoice_id)).scalar_one(),
        "lines": db.execute(select(func.count(InvoiceLine.id)).where(InvoiceLine.invoice_id == invoice_id)).scalar_one(),
        "payments": db.execute(select(func.count(Payment.id)).where(Payment.invoice_id == invoice_id)).scalar_one(),
        "orders": db.execute(select(func.count(TestOrder.id)).join(InvoiceLine, InvoiceLine.id == TestOrder.invoice_line_id)
                             .where(InvoiceLine.invoice_id == invoice_id)).scalar_one(),
    }


def test_creator_discards_own_draft_and_audit_survives(client, db_session):
    draft = _make_draft(client, db_session)
    temp = db_session.get(Invoice, draft["id"]).temp_invoice_id
    # a draft has no operational side effects (the premise the discard relies on)
    assert _counts(db_session, draft["id"]) == {"invoices": 1, "lines": 0, "payments": 0, "orders": 0}
    assert client.delete(f"/invoices/{draft['id']}/draft", headers=TECH_KAMAL_HEADERS).status_code == 403
    res = client.delete(f"/invoices/{draft['id']}/draft", headers=RECEPTIONIST_HEADERS)
    assert res.status_code == 200, res.text
    assert res.json()["discarded_invoice_id"] == draft["id"]
    db_session.expire_all()
    assert _counts(db_session, draft["id"]) == {"invoices": 0, "lines": 0, "payments": 0, "orders": 0}
    audit = _audits(db_session, "INVOICE_DRAFT_DISCARDED", draft["id"])
    assert len(audit) == 1 and temp in audit[0].before_value and audit[0].actor_id is not None
    assert client.get(f"/invoices/{draft['id']}", headers=RECEPTIONIST_HEADERS).status_code == 404
    assert client.delete(f"/invoices/{draft['id']}/draft", headers=RECEPTIONIST_HEADERS).status_code == 404


def test_other_staff_cannot_discard_but_admin_and_owner_can(client, db_session):
    d1 = _make_draft(client, db_session)  # created by the receptionist
    assert client.delete(f"/invoices/{d1['id']}/draft", headers=CASHIER_HEADERS).status_code == 403
    db_session.expire_all()
    assert db_session.get(Invoice, d1["id"]) is not None
    assert client.delete(f"/invoices/{d1['id']}/draft", headers=ADMIN_HEADERS).status_code == 200
    d2 = _make_draft(client, db_session)
    assert client.delete(f"/invoices/{d2['id']}/draft", headers=OWNER_HEADERS).status_code == 200
    db_session.expire_all()
    assert db_session.get(Invoice, d1["id"]) is None and db_session.get(Invoice, d2["id"]) is None
    assert len(_audits(db_session, "INVOICE_DRAFT_DISCARDED", d1["id"])) == 1


def test_non_draft_invoices_cannot_be_discarded(client, db_session):
    code = _test(db_session, sample_type="Blood")
    inv = _invoice(client, db_session, [code])  # CONFIRMED
    res = client.delete(f"/invoices/{inv['id']}/draft", headers=ADMIN_HEADERS)
    assert res.status_code == 409 and "DRAFT" in res.json()["detail"]
    row = db_session.get(Invoice, inv["id"])
    db_session.refresh(row)
    row.status = "CANCELLED"
    db_session.commit()
    assert client.delete(f"/invoices/{inv['id']}/draft", headers=OWNER_HEADERS).status_code == 409
    db_session.expire_all()
    assert db_session.get(Invoice, inv["id"]) is not None
    assert not _audits(db_session, "INVOICE_DRAFT_DISCARDED", inv["id"])
    row = db_session.get(Invoice, inv["id"])
    row.status = "CONFIRMED"
    db_session.commit()


def test_draft_with_operational_records_is_refused_not_deleted(client, db_session):
    draft = _make_draft(client, db_session)
    inv = db_session.get(Invoice, draft["id"])
    visit_id = db_session.execute(select(Visit.id).order_by(Visit.id)).scalars().first()
    inv.visit_id = visit_id  # a draft that somehow has a visit
    db_session.commit()
    res = client.delete(f"/invoices/{draft['id']}/draft", headers=ADMIN_HEADERS)
    assert res.status_code == 409 and "operational" in res.json()["detail"]
    db_session.expire_all()
    inv = db_session.get(Invoice, draft["id"])
    assert inv is not None and not _audits(db_session, "INVOICE_DRAFT_DISCARDED", draft["id"])
    inv.visit_id = None
    db_session.commit()
    assert client.delete(f"/invoices/{draft['id']}/draft", headers=ADMIN_HEADERS).status_code == 200


# ===========================================================================
# Audit log viewer
# ===========================================================================
def test_audit_view_permission_matrix(client, db_session):
    assert client.get("/audit-logs", headers=OWNER_HEADERS).status_code == 200
    assert client.get("/audit-logs/meta", headers=OWNER_HEADERS).status_code == 200
    for h in (ADMIN_HEADERS, RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.get("/audit-logs", headers=h).status_code == 403
        assert client.get("/audit-logs/meta", headers=h).status_code == 403
    doctor = _new_user("DOCTOR")
    assert _login(doctor["username"]).get("/audit-logs").status_code == 403
    # an Owner can grant it to an Admin; it can never be granted to LAB_TECH / DOCTOR
    admin2 = _new_user("ADMIN")
    assert client.put(f"/users/{admin2['id']}/permissions", headers=OWNER_HEADERS, json={"overrides": {"audit.view": True}}).status_code == 200
    assert _login(admin2["username"]).get("/audit-logs").status_code == 200
    tech = _new_user("LAB_TECH", lab_section="HEMATOLOGY")
    assert client.put(f"/users/{tech['id']}/permissions", headers=OWNER_HEADERS, json={"overrides": {"audit.view": True}}).status_code == 400
    assert client.put(f"/users/{doctor['id']}/permissions", headers=OWNER_HEADERS, json={"overrides": {"audit.view": True}}).status_code == 400
    # an Admin without the permission cannot hand it out (no escalation)
    other = _new_user("RECEPTIONIST")
    assert client.put(f"/users/{other['id']}/permissions", headers=ADMIN_HEADERS, json={"overrides": {"audit.view": True}}).status_code == 403


def test_audit_log_returns_prompt11_rows_filters_and_is_read_only(client, db_session):
    # produce one row of every kind this prompt adds
    code = _test(db_session, sample_type="Blood")
    test_id = db_session.execute(select(Test.id).where(Test.code == code)).scalar_one()
    ref = _new_referrer(client, "Dr Audit")
    user = _new_user("RECEPTIONIST")
    draft = _make_draft(client, db_session)
    assert _delete(client, f"/tests/{test_id}/delete", ADMIN_HEADERS, "audit probe test").status_code == 200
    assert client.post(f"/tests/{test_id}/restore", headers=ADMIN_HEADERS).status_code == 200
    assert _delete(client, f"/referrers/{ref['id']}/delete", ADMIN_HEADERS, "audit probe ref").status_code == 200
    assert _delete(client, f"/users/{user['id']}/delete", ADMIN_HEADERS, "audit probe user").status_code == 200
    assert client.delete(f"/invoices/{draft['id']}/draft", headers=ADMIN_HEADERS).status_code == 200

    def q(**params):
        res = client.get("/audit-logs", headers=OWNER_HEADERS, params={"size": 200, **params})
        assert res.status_code == 200, res.text
        return res.json()

    expectations = [
        ("TEST_SOFT_DELETED", "TEST", test_id, "audit probe test"),
        ("TEST_RESTORED", "TEST", test_id, None),
        ("REFERRER_SOFT_DELETED", "REFERRER", ref["id"], "audit probe ref"),
        ("USER_SOFT_DELETED", "STAFF", user["id"], "audit probe user"),
        ("INVOICE_DRAFT_DISCARDED", "INVOICE", draft["id"], None),
    ]
    admin_id = db_session.execute(select(Staff.id).where(Staff.username == "admin_tariq")).scalar_one()
    for action, entity, eid, reason in expectations:
        rows = [r for r in q(action=action, entity_type=entity)["items"] if r["entity_id"] == str(eid)]
        assert len(rows) == 1, (action, rows)
        assert rows[0]["actor_id"] == admin_id and rows[0]["acting_role"] == "ADMIN" and rows[0]["actor_name"]
        assert rows[0]["reason"] == reason
    # filters narrow results
    only = q(action="TEST_SOFT_DELETED")
    assert only["total"] >= 1 and {r["action"] for r in only["items"]} == {"TEST_SOFT_DELETED"}
    assert {r["entity_type"] for r in q(entity_type="REFERRER")["items"]} == {"REFERRER"}
    by_actor = q(actor_id=admin_id)
    assert by_actor["items"] and {r["actor_id"] for r in by_actor["items"]} == {admin_id}
    today = date.today()
    assert q(action="TEST_SOFT_DELETED", date_from=(today - timedelta(days=1)).isoformat(),
             date_to=(today + timedelta(days=1)).isoformat())["total"] >= 1
    assert q(action="TEST_SOFT_DELETED", date_from=(today + timedelta(days=2)).isoformat())["total"] == 0
    assert q(action="TEST_SOFT_DELETED", date_to=(today - timedelta(days=2)).isoformat())["total"] == 0
    # pagination + newest first; existing (pre-Prompt-11) rows are included
    page = client.get("/audit-logs", headers=OWNER_HEADERS, params={"size": 2, "page": 1}).json()
    assert len(page["items"]) == 2 and page["total"] > 2 and page["pages"] >= 2
    stamps = [r["created_at"] for r in q()["items"]]
    assert stamps == sorted(stamps, reverse=True)
    assert any(r["action"] in ("USER_CREATED", "CREATE_REFERRER", "SAVE_INVOICE_DRAFT") for r in q(size=200)["items"])
    meta = client.get("/audit-logs/meta", headers=OWNER_HEADERS).json()
    assert "TEST_SOFT_DELETED" in meta["actions"] and "TEST" in meta["entity_types"]

    # read only: the router exposes GET operations only
    from backend.app.main import app
    for path, ops in app.openapi()["paths"].items():
        if path.startswith("/api/v1/audit-logs"):
            assert set(ops) == {"get"}, (path, ops)
    assert client.post("/audit-logs", headers=OWNER_HEADERS, json={}).status_code == 405
    assert client.delete("/audit-logs", headers=OWNER_HEADERS).status_code == 405
    assert client.put("/audit-logs", headers=OWNER_HEADERS, json={}).status_code == 405

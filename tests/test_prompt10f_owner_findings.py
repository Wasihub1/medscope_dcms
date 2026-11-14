"""
Prompt 10F — owner browser findings and decisions:
F1 Assigned Tests view (view only for front desk, reassign for Admin/Owner until COMPLETED),
F2 Preview of a saved result (DRAFT or ENTERED), F3 one shared Ready definition,
F4 A5 sample rule (NULL sample_type on a non-imaging test = sample required),
F5 A11 empty room demotes assigned-only orders to UNASSIGNED.
Runs only against medscope_test (conftest guard). Passwords are generated per run.
"""
import pathlib
import secrets
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.permissions import effective_permissions
from backend.app.core.samples import is_imaging_test, requires_sample
from backend.app.core.security import CurrentActor
from backend.app.models.audit import AuditLog
from backend.app.models.invoice import Invoice
from backend.app.models.patient import Patient
from backend.app.models.result import Result
from backend.app.models.test import Test
from backend.app.models.test_order import AssignmentHistory, TestOrder
from backend.app.models.user import Staff
from tests.conftest import (
    ADMIN_HEADERS,
    OWNER_HEADERS,
    RECEPTIONIST_HEADERS,
    TECH_KAMAL_HEADERS,
    TECH_NASRIN_AUTH_TOKEN,
)
NASRIN_HEADERS = {"Authorization": f"Bearer {TECH_NASRIN_AUTH_TOKEN}", "X-Requested-With": "XMLHttpRequest"}

PASSWORD = "R" + secrets.token_urlsafe(16)  # generated per run; never stored
TENANT = "center-seba-01"
MONEY_WORDS = ("price", "amount", "net", "gross", "due", "paid", "discount", "commission", "fee", "refund", "balance")
REPO = pathlib.Path(__file__).resolve().parent.parent


def _client():
    from backend.app.main import app
    return TestClient(app, base_url="http://testserver/api/v1", headers={"X-Requested-With": "XMLHttpRequest"})


def _new_user(role, creator=ADMIN_HEADERS, **extra):
    body = {"username": f"p10f_{role.lower()}_{uuid4().hex[:8]}", "display_name": f"P10F {role}", "password": PASSWORD, "role": role}
    body.update(extra)
    res = _client().post("/users", headers=creator, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _login(username):
    c = _client()
    res = c.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return c


def _test(db, **kw):
    code = f"P10F_{uuid4().hex[:8].upper()}"
    fields = dict(tenant_id=TENANT, code=code, name=f"10F probe {code}", department="Clinical Pathology", price=200,
                  sample_type=None, performing_role="LAB_TECH", requires_doctor=False, report_template="NUMERIC_TABLE",
                  approval_rule="TECHNICIAN_FINAL", is_outsourced=False, active=True, lab_section="HEMATOLOGY")
    fields.update(kw)
    db.add(Test(**fields))
    db.commit()
    return code


def _invoice(client, db, codes):
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json={
        "patient_id": pid, "age_value": 30, "gender": "Male",
        "lines": [{"test_id": db.execute(select(Test.id).where(Test.code == c)).scalar_one()} for c in codes],
        "initial_payment_amount": 0, "initial_payment_method": "CASH",
    })
    assert res.status_code == 201, res.text
    return res.json()


def _order(db, invoice_id, code):
    db.expire_all()
    inv = db.get(Invoice, invoice_id)
    return next(l.test_order for l in inv.lines if l.test_code_snapshot == code)


def _keys(d, prefix=""):
    out = []
    for k, v in d.items():
        out.append(k)
        if isinstance(v, dict):
            out += _keys(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    out += _keys(x)
    return out


def _no_money(d):
    return not any(any(w in k.lower() for w in MONEY_WORDS) for k in _keys(d))


def _save(client, headers, oid, status_="ENTERED", value="5"):
    return client.post(f"/worklist/{oid}/result", headers=headers, json={
        "status": status_, "findings": "probe", "items": [{"component_name": "Probe", "component_code": "PRB", "value": value, "unit": "u", "reference_range": "1-9"}],
    })


def _ids(c, headers=None, **params):
    res = c.get("/worklist", headers=headers, params={"limit": 200, **params}) if headers else c.get("/worklist", params={"limit": 200, **params})
    assert res.status_code == 200, res.text
    return {i["test_order_id"] for i in res.json()}


def _summary(c, headers=None):
    res = c.get("/worklist/summary", headers=headers) if headers else c.get("/worklist/summary")
    assert res.status_code == 200, res.text
    return res.json()


def _audits(db, action, entity_id):
    db.expire_all()
    return db.execute(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == str(entity_id))).scalars().all()


# ===========================================================================
# F1 — Assigned Tests view
# ===========================================================================
def test_f1_assigned_view_roles_payload_and_reassign_rules(client, db_session):
    code = _test(db_session, sample_type="Blood")
    inv = _invoice(client, db_session, [code])
    order = _order(db_session, inv["id"], code)
    assert order.status == "ASSIGNED" and order.lab_section == "HEMATOLOGY"

    # RECEPTIONIST: view only (no reassign control decided server-side, backend refuses the call)
    rows = client.get("/assignments/orders", headers=RECEPTIONIST_HEADERS, params={"q": inv["invoice_no"]})
    assert rows.status_code == 200, rows.text
    row = next(r for r in rows.json() if r["test_order_id"] == order.id)
    assert row["can_reassign"] is False and "View only" in row["reassign_block_reason"]
    assert row["lab_section"] == "HEMATOLOGY" and row["assignment_state"] == "ASSIGNED"
    assert row["technician_names"], "the room's active technician names are listed"
    assert row["invoice_no"] == inv["invoice_no"] and row["patient_name"] and row["test_name"]
    assert "urgent" in row and "created_at" in row and "status" in row
    for r in rows.json():
        assert _no_money(r), r
    assert client.post(f"/worklist/{order.id}/reassign", headers=RECEPTIONIST_HEADERS,
                       json={"lab_section": "BIOCHEMISTRY"}).status_code == 403

    # LAB_TECH and DOCTOR cannot use the view
    assert client.get("/assignments/orders", headers=TECH_KAMAL_HEADERS).status_code == 403
    doctor = _login(_new_user("DOCTOR")["username"])
    assert doctor.get("/assignments/orders").status_code == 403

    # ADMIN can reassign before COMPLETED (existing 10E endpoint; audit + append-only history)
    admin_row = next(r for r in client.get("/assignments/orders", headers=ADMIN_HEADERS, params={"q": inv["invoice_no"]}).json()
                     if r["test_order_id"] == order.id)
    assert admin_row["can_reassign"] is True and admin_row["reassign_block_reason"] is None
    res = client.post(f"/worklist/{order.id}/reassign", headers=ADMIN_HEADERS, json={"lab_section": "BIOCHEMISTRY", "reason": "10F admin"})
    assert res.status_code == 200, res.text
    assert _audits(db_session, "REASSIGN_ROOM", order.id)
    assert db_session.execute(select(AssignmentHistory).where(AssignmentHistory.test_order_id == order.id)).scalars().first() is not None
    # the receiving room sees it on its next fetch; the old room no longer does
    nasrin = db_session.execute(select(Staff).where(Staff.username == "tech_nasrin")).scalar_one()
    if nasrin.lab_section == "BIOCHEMISTRY" and nasrin.active:
        assert order.id in _ids(client, NASRIN_HEADERS)
    assert order.id not in _ids(client, TECH_KAMAL_HEADERS)
    moved = next(r for r in client.get("/assignments/orders", headers=ADMIN_HEADERS, params={"q": inv["invoice_no"]}).json()
                 if r["test_order_id"] == order.id)
    assert moved["lab_section"] == "BIOCHEMISTRY"

    # OWNER can reassign too
    res = client.post(f"/worklist/{order.id}/reassign", headers=OWNER_HEADERS, json={"lab_section": "HEMATOLOGY", "reason": "10F owner"})
    assert res.status_code == 200, res.text

    # COMPLETED: refused with a clear 409, and the list says why
    assert client.post(f"/worklist/{order.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, order.id).status_code == 200
    db_session.expire_all()
    assert db_session.get(TestOrder, order.id).status == "COMPLETED"
    late = client.post(f"/worklist/{order.id}/reassign", headers=ADMIN_HEADERS, json={"lab_section": "BIOCHEMISTRY"})
    assert late.status_code == 409 and "COMPLETED" in late.json()["detail"]
    done = next(r for r in client.get("/assignments/orders", headers=OWNER_HEADERS, params={"q": inv["invoice_no"]}).json()
                if r["test_order_id"] == order.id)
    assert done["can_reassign"] is False and done["reassign_block_reason"].startswith("Completed")


def test_f1_not_performed_order_cannot_be_reassigned_and_filters_work(client, db_session):
    code = _test(db_session, sample_type="Blood")
    inv = _invoice(client, db_session, [code])
    order = _order(db_session, inv["id"], code)
    assert client.post(f"/worklist/{order.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    assert client.post(f"/worklist/{order.id}/reject-sample", headers=TECH_KAMAL_HEADERS,
                       json={"rejection_reason": "Hemolyzed specimen", "spoil_type": "REJECTED"}).status_code == 200
    res = client.post(f"/worklist/{order.id}/reassign", headers=ADMIN_HEADERS, json={"lab_section": "BIOCHEMISTRY"})
    assert res.status_code == 409 and "Not performed" in res.json()["detail"]
    np_ids = {r["test_order_id"] for r in client.get("/assignments/orders", headers=ADMIN_HEADERS,
                                                    params={"status": "NOT_PERFORMED", "q": inv["invoice_no"]}).json()}
    assert order.id in np_ids
    hem = client.get("/assignments/orders", headers=ADMIN_HEADERS, params={"lab_section": "HEMATOLOGY", "q": inv["invoice_no"]}).json()
    assert all(r["lab_section"] == "HEMATOLOGY" for r in hem)
    assert client.get("/assignments/orders", headers=ADMIN_HEADERS, params={"status": "BOGUS"}).status_code == 400


# ===========================================================================
# F2 / F3 — Preview and the one shared Ready definition
# ===========================================================================
def test_f2_draft_is_previewable_marked_draft_and_not_ready(client, db_session):
    code = _test(db_session, sample_type="Blood")
    inv = _invoice(client, db_session, [code])
    order = _order(db_session, inv["id"], code)
    assert client.post(f"/worklist/{order.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, order.id, "DRAFT", value="12").status_code == 200
    # the grid row (refetch after save) carries has_result -> Preview action
    item = next(i for i in client.get("/worklist", headers=TECH_KAMAL_HEADERS, params={"q": inv["invoice_no"]}).json()
                if i["test_order_id"] == order.id)
    assert item["has_result"] is True and item["result_status"] == "DRAFT" and item["report_ready"] is False
    prev = client.get(f"/worklist/{order.id}/result-preview", headers=TECH_KAMAL_HEADERS)
    assert prev.status_code == 200, prev.text
    body = prev.json()
    assert body["is_draft"] is True and body["result_status"] == "DRAFT" and body["is_ready"] is False
    assert body["items"][0]["component_name"] == "Probe" and body["items"][0]["reference_range"] == "1-9"
    assert _no_money(body)
    # another room's technician cannot preview it
    nasrin = db_session.execute(select(Staff).where(Staff.username == "tech_nasrin")).scalar_one()
    if nasrin.lab_section != "HEMATOLOGY":
        assert client.get(f"/worklist/{order.id}/result-preview", headers=NASRIN_HEADERS).status_code == 403
    # no saved result -> 404 with a plain message
    code2 = _test(db_session, sample_type="Blood")
    inv2 = _invoice(client, db_session, [code2])
    o2 = _order(db_session, inv2["id"], code2)
    nores = client.get(f"/worklist/{o2.id}/result-preview", headers=ADMIN_HEADERS)
    assert nores.status_code == 404 and "No result" in nores.json()["detail"]


def test_f3_entered_is_ready_without_complete_and_lists_agree(client, db_session):
    # BOTH_SIGNATURES: submitting the result leaves the order IN_PROGRESS (no operational Complete)
    ready_code = _test(db_session, sample_type="Serum", approval_rule="BOTH_SIGNATURES")
    draft_code = _test(db_session, sample_type="Serum")
    cancel_code = _test(db_session, sample_type="Serum", approval_rule="BOTH_SIGNATURES")
    reject_code = _test(db_session, sample_type="Serum", approval_rule="BOTH_SIGNATURES")
    inv = _invoice(client, db_session, [ready_code, draft_code, cancel_code, reject_code, "USG_W_A"])
    o_ready, o_draft, o_cancel, o_reject = (_order(db_session, inv["id"], c) for c in (ready_code, draft_code, cancel_code, reject_code))
    o_doc = _order(db_session, inv["id"], "USG_W_A")
    for o in (o_ready, o_draft, o_cancel, o_reject):
        assert client.post(f"/worklist/{o.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, o_ready.id).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, o_draft.id, "DRAFT").status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, o_cancel.id).status_code == 200
    assert client.post(f"/worklist/{o_cancel.id}/status", headers=ADMIN_HEADERS, json={"status": "CANCELLED"}).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, o_reject.id).status_code == 200
    assert client.post(f"/worklist/{o_reject.id}/reject-sample", headers=TECH_KAMAL_HEADERS,
                       json={"rejection_reason": "Clotted specimen", "spoil_type": "REJECTED"}).status_code == 200
    assert _save(client, ADMIN_HEADERS, o_doc.id).status_code == 200  # doctor-routed -> AWAITING_DOCTOR
    db_session.expire_all()
    assert db_session.get(TestOrder, o_ready.id).status == "IN_PROGRESS"  # not operationally completed
    assert db_session.get(TestOrder, o_doc.id).status == "AWAITING_DOCTOR"
    assert db_session.get(TestOrder, o_reject.id).outcome == "NOT_PERFORMED"

    for headers in (TECH_KAMAL_HEADERS, ADMIN_HEADERS):
        ready_ids = _ids(client, headers, status="READY")
        assert o_ready.id in ready_ids
        assert not ready_ids & {o_draft.id, o_cancel.id, o_reject.id, o_doc.id}
        count = _summary(client, headers)["ready_count"]
        if count <= 200:
            assert count == len(ready_ids)  # tile count == rows
        # the row flag uses the same definition
        flags = {i["test_order_id"]: i["report_ready"] for i in client.get("/worklist", headers=headers, params={"q": inv["invoice_no"], "limit": 200}).json()}
        assert flags[o_ready.id] is True and flags[o_draft.id] is False
        assert flags.get(o_reject.id, False) is False and flags.get(o_doc.id, False) is False

    # sidebar Ready Reports (all rooms) agrees with the Admin (all rooms) Lab list
    side = client.get("/reports/ready", headers=ADMIN_HEADERS, params={"limit": 200})
    assert side.status_code == 200, side.text
    side_ids = {r["test_order_id"] for r in side.json()}
    assert o_ready.id in side_ids and not side_ids & {o_draft.id, o_cancel.id, o_reject.id, o_doc.id}
    admin_ready = _ids(client, ADMIN_HEADERS, status="READY")
    if len(side_ids) < 200 and len(admin_ready) < 200:
        assert side_ids == admin_ready
    row = next(r for r in side.json() if r["test_order_id"] == o_ready.id)
    assert row["lab_section"] == "HEMATOLOGY" and row["result_entered_at"] and row["invoice_no"] == inv["invoice_no"]
    # room filter and search
    assert o_ready.id in {r["test_order_id"] for r in client.get("/reports/ready", headers=ADMIN_HEADERS,
                                                                 params={"lab_section": "HEMATOLOGY", "q": inv["invoice_no"]}).json()}
    assert o_ready.id not in {r["test_order_id"] for r in client.get("/reports/ready", headers=ADMIN_HEADERS,
                                                                     params={"lab_section": "BIOCHEMISTRY", "q": inv["invoice_no"]}).json()}
    # Ready does not create report_versions (Module 14 not built)
    db_session.expire_all()
    assert db_session.get(TestOrder, o_ready.id).report_version is None
    # front-desk preview of a Ready result is money-free
    prev = client.get(f"/reports/ready/{o_ready.id}/preview", headers=RECEPTIONIST_HEADERS)
    assert prev.status_code == 200 and prev.json()["is_ready"] is True and _no_money(prev.json())


def test_f3_money_fields_only_for_money_roles(client, db_session):
    code = _test(db_session, sample_type="Serum")
    inv = _invoice(client, db_session, [code])
    o = _order(db_session, inv["id"], code)
    assert client.post(f"/worklist/{o.id}/sample-taken", headers=TECH_KAMAL_HEADERS, json={}).status_code == 200
    assert _save(client, TECH_KAMAL_HEADERS, o.id).status_code == 200
    rec_row = next(r for r in client.get("/reports/ready", headers=RECEPTIONIST_HEADERS, params={"q": inv["invoice_no"]}).json()
                   if r["test_order_id"] == o.id)
    assert "invoice_due" in rec_row and "has_due" in rec_row and rec_row["has_due"] is (rec_row["invoice_due"] > 0)
    # a front-desk user without payment.view still sees Ready Reports, but never the due
    restricted = _new_user("RECEPTIONIST", permission_overrides={"payment.view": False})
    c = _login(restricted["username"])
    rows = c.get("/reports/ready", params={"q": inv["invoice_no"]})
    assert rows.status_code == 200, rows.text
    for r in rows.json():
        assert _no_money(r), r
    # technicians and doctors cannot open the sidebar list at all
    assert client.get("/reports/ready", headers=TECH_KAMAL_HEADERS).status_code == 403
    doctor = _login(_new_user("DOCTOR")["username"])
    assert doctor.get("/reports/ready").status_code == 403
    assert doctor.get(f"/reports/ready/{o.id}/preview").status_code == 403


# ===========================================================================
# F4 — sample rule (A5)
# ===========================================================================
def test_f4_helper_rules_and_single_definition():
    lab = dict(requires_doctor=False, performing_role="LAB_TECH", report_template="NUMERIC_TABLE", department="Clinical Pathology", lab_section=None)
    assert requires_sample(SimpleNamespace(sample_type=None, **lab)) is True       # unknown -> required
    assert requires_sample(SimpleNamespace(sample_type="", **lab)) is True
    for marker in ("None", " none ", "N/A", "n/a", "NA", "No sample", "NO SAMPLE"):
        assert requires_sample(SimpleNamespace(sample_type=marker, **lab)) is False
    assert requires_sample(SimpleNamespace(sample_type="Fresh Stool", **lab)) is True
    # imaging with NULL never needs a sample: department, room and narrative template
    for img in (dict(lab, department="X-Ray & Radiology"), dict(lab, department="Ultrasonography (USG)"),
                dict(lab, lab_section="ULTRASONOGRAPHY"), dict(lab, report_template="NARRATIVE")):
        assert is_imaging_test(SimpleNamespace(sample_type=None, **img)) is True
        assert requires_sample(SimpleNamespace(sample_type=None, **img)) is False
    # doctor-read tissue test is NOT imaging (was imaging in 10E through requires_doctor)
    tissue = dict(lab, requires_doctor=True, performing_role="Specialist Doctor / Designated Lab Technologist")
    assert is_imaging_test(SimpleNamespace(sample_type=None, **tissue)) is False
    assert requires_sample(SimpleNamespace(sample_type=None, **tissue)) is True
    # exactly one definition of each helper in the backend
    defs = {"def requires_sample(": 0, "def is_imaging_test(": 0}
    for f in (REPO / "backend").rglob("*.py"):
        text_ = f.read_text(encoding="utf-8", errors="ignore")
        for k in defs:
            defs[k] += text_.count(k)
        assert "NO_SAMPLE_VALUES" not in text_, f
    assert defs == {"def requires_sample(": 1, "def is_imaging_test(": 1}


def test_f4_null_sample_type_blocks_every_gate_until_sample_taken(client, db_session):
    code = _test(db_session, sample_type=None, department="Clinical Pathology")
    culture = _test(db_session, sample_type=None, report_template="CULTURE_SENSITIVITY", department="Microbiology")
    inv = _invoice(client, db_session, [code, culture])
    o = _order(db_session, inv["id"], code)
    oc = _order(db_session, inv["id"], culture)
    item = next(i for i in client.get("/worklist", headers=ADMIN_HEADERS, params={"q": inv["invoice_no"]}).json() if i["test_order_id"] == o.id)
    assert item["requires_sample"] is True and item["is_imaging"] is False
    for st in ("DRAFT", "ENTERED"):
        res = _save(client, ADMIN_HEADERS, o.id, st)
        assert res.status_code == 409 and res.json()["detail"].startswith("Take the sample before entering results")
    tpl = client.get(f"/worklist/{o.id}/result-template", headers=ADMIN_HEADERS)
    assert tpl.status_code == 400 and "Take the sample" in tpl.json()["detail"]
    done = client.post(f"/worklist/{o.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"})
    assert done.status_code == 400 and "Take the sample before completing" in done.json()["detail"]
    sent = client.post(f"/worklist/{o.id}/outsourced", headers=ADMIN_HEADERS, json={"action": "SENT", "lab_name": "Ref Lab"})
    assert sent.status_code == 400 and "Take the sample" in sent.json()["detail"]
    stage = client.post(f"/worklist/{oc.id}/culture-stage", headers=ADMIN_HEADERS, json={"stage": "INCUBATING"})
    assert stage.status_code == 400 and "Take the sample" in stage.json()["detail"]
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    line = next(l for l in detail["lines"] if l["test_code_snapshot"] == code)
    assert line["sample_status"] == "Awaiting collection"
    db_session.expire_all()
    assert db_session.get(TestOrder, o.id).invoice_line.is_locked is False  # no lock without a sample
    # after Sample Taken: line locks, result and Complete are allowed
    assert client.post(f"/worklist/{o.id}/sample-taken", headers=ADMIN_HEADERS, json={}).status_code == 200
    db_session.expire_all()
    assert db_session.get(TestOrder, o.id).invoice_line.is_locked is True
    assert _save(client, ADMIN_HEADERS, o.id, "DRAFT").status_code == 200
    assert client.post(f"/worklist/{o.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"}).status_code == 200


def test_f4_explicit_marker_and_imaging_proceed_without_sample(client, db_session):
    none_code = _test(db_session, sample_type="None")
    na_code = _test(db_session, sample_type="N/A")
    xray_code = _test(db_session, sample_type=None, department="X-Ray & Radiology", lab_section=None)
    inv = _invoice(client, db_session, [none_code, na_code, xray_code])
    for c in (none_code, na_code):
        o = _order(db_session, inv["id"], c)
        assert _save(client, ADMIN_HEADERS, o.id, "DRAFT").status_code == 200
        assert client.post(f"/worklist/{o.id}/status", headers=ADMIN_HEADERS, json={"status": "COMPLETED"}).status_code == 200
    ox = _order(db_session, inv["id"], xray_code)
    assert _save(client, ADMIN_HEADERS, ox.id, "DRAFT").status_code == 200
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    statuses = {l["test_code_snapshot"]: l["sample_status"] for l in detail["lines"]}
    assert statuses[none_code] == "No sample needed" and statuses[na_code] == "No sample needed"
    assert statuses[xray_code] in ("Awaiting Exam", "PERFORMED")


def test_f4_existing_completed_order_without_sample_is_unaffected(client, db_session):
    # Simulates a legacy order completed under the 10E rule (NULL = no sample): the data is not
    # changed by 10F, it stays COMPLETED, can be previewed and is labelled honestly.
    code = _test(db_session, sample_type=None)
    inv = _invoice(client, db_session, [code])
    o = _order(db_session, inv["id"], code)
    order = db_session.get(TestOrder, o.id)
    db_session.add(Result(tenant_id=TENANT, test_order_id=o.id, result_type="NUMERIC_TABLE", status="ENTERED",
                          findings="legacy", entered_by_id=db_session.execute(select(Staff.id).where(Staff.username == "tech_kamal")).scalar_one()))
    order.status = "COMPLETED"
    db_session.commit()
    prev = client.get(f"/worklist/{o.id}/result-preview", headers=TECH_KAMAL_HEADERS)
    assert prev.status_code == 200 and prev.json()["result_status"] == "ENTERED" and prev.json()["is_ready"] is True
    detail = client.get(f"/invoices/{inv['id']}", headers=RECEPTIONIST_HEADERS).json()
    assert next(l for l in detail["lines"] if l["test_code_snapshot"] == code)["sample_status"] == "Completed without sample"
    db_session.expire_all()
    assert db_session.get(TestOrder, o.id).status == "COMPLETED"
    assert db_session.get(TestOrder, o.id).sample is None


# ===========================================================================
# F5 — empty room demotes assigned-only orders (A11)
# ===========================================================================
def _empty_usg_room(db):
    for s in db.execute(select(Staff).where(Staff.role == "LAB_TECH", Staff.lab_section == "ULTRASONOGRAPHY", Staff.active == True)).scalars():  # noqa: E712
        s.active = False
    db.commit()


def _usg_probe(db):
    return _test(db, sample_type=None, department="Ultrasonography (USG)", lab_section="ULTRASONOGRAPHY",
                 performing_role="USG Technician")


def _usg_orders(client, db, n):
    codes = [_usg_probe(db) for _ in range(n)]
    inv = _invoice(client, db, codes)
    return inv, [_order(db, inv["id"], c) for c in codes]


def test_f5_full_cycle_deactivate_demotes_only_assigned_then_release(client, db_session):
    _empty_usg_room(db_session)
    tech = _new_user("LAB_TECH", lab_section="ULTRASONOGRAPHY")
    inv, (o_plain, o_draft, o_prog, o_scan, o_done) = _usg_orders(client, db_session, 5)
    assert all(o.status == "ASSIGNED" for o in (o_plain, o_draft, o_prog, o_scan, o_done))
    assert _save(client, ADMIN_HEADERS, o_draft.id, "DRAFT").status_code == 200          # ASSIGNED + draft result
    assert client.post(f"/worklist/{o_prog.id}/status", headers=ADMIN_HEADERS, json={"status": "IN_PROGRESS"}).status_code == 200
    assert client.post(f"/worklist/{o_scan.id}/imaging-performed", headers=ADMIN_HEADERS, json={}).status_code == 200
    assert _save(client, ADMIN_HEADERS, o_done.id, "ENTERED").status_code == 200        # -> COMPLETED
    db_session.expire_all()
    before = {o.id: db_session.get(TestOrder, o.id).status for o in (o_draft, o_prog, o_scan, o_done)}
    assert before[o_draft.id] == "ASSIGNED" and before[o_scan.id] == "AWAITING_DOCTOR" and before[o_done.id] == "COMPLETED"

    res = client.post(f"/users/{tech['id']}/deactivate", headers=ADMIN_HEADERS)
    assert res.status_code == 200, res.text
    db_session.expire_all()
    assert db_session.get(TestOrder, o_plain.id).status == "UNASSIGNED"
    assert db_session.get(TestOrder, o_plain.id).lab_section == "ULTRASONOGRAPHY"   # room kept
    for oid, st in before.items():
        assert db_session.get(TestOrder, oid).status == st, oid                      # progress untouched
    assert len(_audits(db_session, "ORDER_UNASSIGNED_ROOM_EMPTY", o_plain.id)) == 1
    for oid in before:
        assert not _audits(db_session, "ORDER_UNASSIGNED_ROOM_EMPTY", oid)
    assert _audits(db_session, "USER_DEACTIVATED", tech["id"])
    hist = db_session.execute(select(AssignmentHistory).where(AssignmentHistory.test_order_id == o_plain.id,
                                                               AssignmentHistory.new_assignee == "UNASSIGNED")).scalars().all()
    assert hist, "append-only assignment history row"
    # Admin / Owner see the demoted order
    assert o_plain.id in _ids(client, ADMIN_HEADERS, status="UNASSIGNED")
    assert o_plain.id in {r["test_order_id"] for r in client.get("/assignments/orders", headers=OWNER_HEADERS,
                                                                 params={"status": "UNASSIGNED", "q": inv["invoice_no"]}).json()}
    row = next(r for r in client.get("/assignments/orders", headers=ADMIN_HEADERS, params={"q": inv["invoice_no"]}).json() if r["test_order_id"] == o_plain.id)
    assert row["assignment_state"] == "UNASSIGNED" and row["technician_names"] == []

    # a technician joins: only the UNASSIGNED order is released; nothing else is touched
    _new_user("LAB_TECH", lab_section="ULTRASONOGRAPHY")
    db_session.expire_all()
    assert db_session.get(TestOrder, o_plain.id).status == "ASSIGNED"
    assert _audits(db_session, "ORDER_ROOM_RELEASED", o_plain.id)
    for oid, st in before.items():
        assert db_session.get(TestOrder, oid).status == st, oid
        assert not _audits(db_session, "ORDER_ROOM_RELEASED", oid)


def test_f5_room_change_and_role_change_also_demote(client, db_session):
    _empty_usg_room(db_session)
    tech = _new_user("LAB_TECH", lab_section="ULTRASONOGRAPHY")
    _, (o1,) = _usg_orders(client, db_session, 1)
    assert o1.status == "ASSIGNED"
    res = client.patch(f"/users/{tech['id']}", headers=ADMIN_HEADERS, json={"lab_section": "MICROBIOLOGY"})
    assert res.status_code == 200, res.text
    db_session.expire_all()
    assert db_session.get(TestOrder, o1.id).status == "UNASSIGNED"
    assert _audits(db_session, "ORDER_UNASSIGNED_ROOM_EMPTY", o1.id)
    # moving back into the room releases it
    assert client.patch(f"/users/{tech['id']}", headers=ADMIN_HEADERS, json={"lab_section": "ULTRASONOGRAPHY"}).status_code == 200
    db_session.expire_all()
    assert db_session.get(TestOrder, o1.id).status == "ASSIGNED"

    # role change away from LAB_TECH
    _, (o2,) = _usg_orders(client, db_session, 1)
    assert o2.status == "ASSIGNED"
    res = client.put(f"/users/{tech['id']}/role", headers=ADMIN_HEADERS, json={"role": "RECEPTIONIST"})
    assert res.status_code == 200, res.text
    db_session.expire_all()
    assert db_session.get(TestOrder, o2.id).status == "UNASSIGNED"
    assert db_session.get(TestOrder, o1.id).status == "UNASSIGNED"
    assert _audits(db_session, "ORDER_UNASSIGNED_ROOM_EMPTY", o2.id) and _audits(db_session, "USER_ROLE_CHANGED", tech["id"])


def test_f5_demotion_is_in_the_same_transaction_as_the_user_change(client, db_session):
    from backend.app.services.user_admin_service import set_user_active
    _empty_usg_room(db_session)
    tech = _new_user("LAB_TECH", lab_section="ULTRASONOGRAPHY")
    _, (o,) = _usg_orders(client, db_session, 1)
    admin = db_session.execute(select(Staff).where(Staff.role == "ADMIN", Staff.active == True)).scalars().first()  # noqa: E712
    actor = CurrentActor(id=admin.id, tenant_id=admin.tenant_id, username=admin.username, display_name=admin.display_name,
                         role=admin.role, permissions=effective_permissions(admin.role, {}))
    staff = db_session.get(Staff, tech["id"])
    set_user_active(db_session, actor, staff, False)
    # inside the open transaction: user change, demotion and both audit rows are pending together
    assert db_session.get(TestOrder, o.id).status == "UNASSIGNED"
    assert db_session.execute(select(AuditLog).where(AuditLog.action == "ORDER_UNASSIGNED_ROOM_EMPTY", AuditLog.entity_id == str(o.id))).scalars().first()
    assert db_session.execute(select(AuditLog).where(AuditLog.action == "USER_DEACTIVATED", AuditLog.entity_id == str(tech["id"]))).scalars().first()
    db_session.rollback()  # nothing is half-applied
    db_session.expire_all()
    assert db_session.get(Staff, tech["id"]).active is True
    assert db_session.get(TestOrder, o.id).status == "ASSIGNED"
    assert not _audits(db_session, "ORDER_UNASSIGNED_ROOM_EMPTY", o.id)

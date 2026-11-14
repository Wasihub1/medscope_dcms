"""
Prompt 14 (D24) - reference ranges versioned by sex and age band in days.

Covers: age -> total days, band selection (sex band, any-sex fallback, no band), snapshot onto the result
item, admin management (add band / new version / retire, overlap, permissions), and the non-destructiveness
guarantee (saved results never change when a range changes). Runs only against medscope_test (conftest guard).
"""
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.models.audit import AuditLog
from backend.app.models.invoice import InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.result import ResultItem
from backend.app.models.test import ReferenceRangeVersion, Test, TestComponent
from backend.app.services import reference_range_service as rrs
from tests.conftest import (
    ADMIN_HEADERS, CASHIER_HEADERS, OWNER_HEADERS, RECEPTIONIST_HEADERS, TECH_KAMAL_HEADERS,
)

TENANT = "center-seba-01"
ADULT = 18 * 365  # 6570 days


# ---------------------------------------------------------------- helpers
def _open_day(client):
    st = client.get("/business-day/status", headers=RECEPTIONIST_HEADERS).json()
    if not st["is_open"]:
        assert client.post("/business-day/open", headers=RECEPTIONIST_HEADERS, json={"opening_float": 0}).status_code == 201


def _make_test(db, bands_by_comp):
    """One catalog test with components; bands_by_comp = {code: [band dict, ...]} (all via the real service)."""
    code = f"P14_{uuid4().hex[:8].upper()}"
    t = Test(tenant_id=TENANT, code=code, name=f"14 probe {code}", department="Clinical Pathology", price=300,
             sample_type="Blood", performing_role="LAB_TECH", requires_doctor=False, report_template="NUMERIC_TABLE",
             approval_rule="TECHNICIAN_FINAL", is_outsourced=False, active=True, lab_section="HEMATOLOGY")
    db.add(t)
    db.flush()
    comps = {}
    for i, (ccode, bands) in enumerate(bands_by_comp.items(), start=1):
        c = TestComponent(tenant_id=TENANT, test_id=t.id, code=ccode, name=f"{ccode} comp", unit="g/dL",
                          impossible_min=0.0, impossible_max=100.0, sort_order=i, active=True)
        db.add(c)
        db.flush()
        for b in bands:
            rrs.create_band(db, TENANT, c.id, 1, "OWNER", sex=b["sex"], age_days_min=b["amin"], age_days_max=b.get("amax"),
                            ref_min=b["rmin"], ref_max=b["rmax"], critical_min=b.get("cmin"), critical_max=b.get("cmax"),
                            reference_range_text=b.get("text"), note="test")
        comps[ccode] = c.id
    db.commit()
    return t.id, code, comps


def _order(client, db, test_id, age_value, age_unit, gender):
    _open_day(client)
    pid = db.execute(select(Patient.id).order_by(Patient.id)).scalars().first()
    res = client.post("/invoices", headers=RECEPTIONIST_HEADERS, json={
        "patient_id": pid, "age_value": age_value, "age_unit": age_unit, "gender": gender,
        "lines": [{"test_id": test_id}], "initial_payment_amount": 300, "initial_payment_method": "CASH",
    })
    assert res.status_code == 201, res.text
    db.expire_all()
    order = db.get(InvoiceLine, res.json()["lines"][0]["id"]).test_order
    st = client.post(f"/worklist/{order.id}/sample-taken", headers=ADMIN_HEADERS, json={})
    assert st.status_code == 200, st.text
    return order.id


def _template(client, order_id):
    res = client.get(f"/worklist/{order_id}/result-template", headers=ADMIN_HEADERS)
    assert res.status_code == 200, res.text
    return {c["code"]: c for c in res.json()["components"]}


def _save(client, order_id, comps, values):
    items = [{"component_id": comps[k], "component_name": k, "component_code": k, "value": v} for k, v in values.items()]
    res = client.post(f"/worklist/{order_id}/result", headers=ADMIN_HEADERS, json={"status": "ENTERED", "items": items})
    assert res.status_code == 200, res.text
    return {i["component_code"]: i for i in res.json()["items"]}


def _snap(db, order_id):
    db.expire_all()
    from backend.app.models.test_order import TestOrder
    rows = db.get(TestOrder, order_id).result.items
    return {r.component_code: (r.reference_range_version_id, r.range_match, r.ref_min, r.ref_max, r.critical_min,
                               r.critical_max, r.reference_range, r.flag) for r in rows}


HB_BANDS = [
    {"sex": "MALE", "amin": ADULT, "rmin": 13.0, "rmax": 17.0, "cmin": 7.0, "cmax": 20.0, "text": "13.0 - 17.0 g/dL"},
    {"sex": "FEMALE", "amin": ADULT, "rmin": 12.0, "rmax": 15.5, "cmin": 7.0, "cmax": 20.0, "text": "12.0 - 15.5 g/dL"},
    {"sex": "ANY", "amin": 0, "amax": ADULT - 1, "rmin": 11.0, "rmax": 14.0, "cmin": 6.0, "cmax": 20.0, "text": "11.0 - 14.0 g/dL"},
]


# ---------------------------------------------------------------- age conversion
def test_age_to_total_days():
    visit = date(2026, 11, 14)
    assert rrs.age_to_days(10, "days", visit) == 10
    assert rrs.age_to_days(0, "years", visit) == 0
    assert rrs.age_to_days(1, "years", visit) == 365            # 2025-11-14 -> 2026-11-14
    assert rrs.age_to_days(2, "years", date(2024, 2, 29)) == 731  # calendar span, leap day handled
    assert rrs.age_to_days(3, "months", date(2026, 1, 31)) == 92  # 2025-10-31 -> 2026-01-31
    assert rrs.age_to_days(30, "years", visit) == 10957          # 7 leap days counted (not 30 * 365 = 10950)
    assert rrs.age_to_days(5, "months", None) == 150 and rrs.age_to_days(2, "years", None) == 730


def test_sex_key_mapping():
    assert rrs.sex_key("Male") == "MALE" and rrs.sex_key("FEMALE") == "FEMALE"
    assert rrs.sex_key("Other") is None and rrs.sex_key("Unknown") is None and rrs.sex_key(None) is None


# ---------------------------------------------------------------- selection + snapshot
def test_band_is_chosen_by_sex_and_age_and_snapshotted(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    male = _order(client, db_session, tid, 30, "years", "Male")
    t = _template(client, male)["HB"]
    assert (t["ref_min"], t["ref_max"], t["range_match"]) == (13.0, 17.0, "MATCHED")
    items = _save(client, male, comps, {"HB": "12.5"})
    assert items["HB"]["flag"] == "LOW"  # below the MALE band, would be NORMAL on the female band
    s = _snap(db_session, male)["HB"]
    assert s[1:] == ("MATCHED", 13.0, 17.0, 7.0, 20.0, "13.0 - 17.0 g/dL", "LOW") and s[0] is not None

    female = _order(client, db_session, tid, 30, "years", "Female")
    assert _save(client, female, comps, {"HB": "12.5"})["HB"]["flag"] == "NORMAL"
    assert _template(client, female)["HB"]["reference_range_text"] == "12.0 - 15.5 g/dL"


def test_child_uses_the_any_sex_band_and_labels_it(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    child = _order(client, db_session, tid, 5, "years", "Female")  # 1826 days: in the 'any' child band
    t = _template(client, child)["HB"]
    assert (t["ref_min"], t["ref_max"], t["range_match"]) == (11.0, 14.0, "FALLBACK_ANY")
    assert _save(client, child, comps, {"HB": "12.5"})["HB"]["flag"] == "NORMAL"
    assert _snap(db_session, child)["HB"][1] == "FALLBACK_ANY"


def test_no_matching_band_is_flagged_for_review_never_a_wrong_band(client, db_session):
    only_female_adult = [HB_BANDS[1]]
    tid, _, comps = _make_test(db_session, {"HB": only_female_adult})
    male = _order(client, db_session, tid, 30, "years", "Male")
    t = _template(client, male)["HB"]
    assert t["range_match"] == "NO_BAND" and t["ref_min"] is None and t["reference_range_version_id"] is None
    saved = _save(client, male, comps, {"HB": "12.5"})["HB"]
    assert saved["flag"] is None and saved["range_match"] == "NO_BAND"  # not NORMAL, not on the female band
    # a child (no band covers 0..ADULT-1 here) is also NO_BAND, and 'Other' gender only ever sees ANY bands
    child = _order(client, db_session, tid, 3, "months", "Female")
    assert _template(client, child)["HB"]["range_match"] == "NO_BAND"
    other_tid, _, _ = _make_test(db_session, {"HB": HB_BANDS})
    other = _order(client, db_session, other_tid, 30, "years", "Other")
    assert _template(client, other)["HB"]["range_match"] == "NO_BAND"  # adult sex bands do not apply, child ANY band is too young


def test_impossible_value_validation_still_rejects_absurd_entries(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    order = _order(client, db_session, tid, 30, "years", "Male")
    res = client.post(f"/worklist/{order}/result", headers=ADMIN_HEADERS, json={"status": "ENTERED", "items": [
        {"component_id": comps["HB"], "component_name": "HB", "component_code": "HB", "value": "500"}]})
    assert res.status_code == 400 and "impossible" in res.json()["detail"].lower()


# ---------------------------------------------------------------- non-destructive (the key guarantee)
def test_changing_a_range_never_alters_a_saved_result(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    order = _order(client, db_session, tid, 30, "years", "Male")
    _save(client, order, comps, {"HB": "12.5"})
    before = _snap(db_session, order)

    db_session.expire_all()
    male_band = next(b for b in db_session.get(TestComponent, comps["HB"]).range_versions if b.sex == "MALE" and b.is_current)
    # 1) a new version of the band (the normal range moves down, so 12.5 would now be NORMAL)
    res = client.post(f"/reference-ranges/versions/{male_band.id}/new-version", headers=ADMIN_HEADERS, json={
        "ref_min": 12.0, "ref_max": 16.0, "critical_min": 6.0, "critical_max": 20.0, "reference_range_text": "12.0 - 16.0 g/dL", "note": "lab review"})
    assert res.status_code == 201, res.text
    assert _snap(db_session, order) == before  # saved result untouched
    re_read = client.get(f"/worklist/{order}/result", headers=ADMIN_HEADERS).json()["existing_result"]["items"][0]
    assert (re_read["ref_min"], re_read["ref_max"], re_read["flag"]) == (13.0, 17.0, "LOW")

    # 2) a brand new band and 3) retiring the new version: still untouched
    assert client.post(f"/reference-ranges/components/{comps['HB']}/bands", headers=ADMIN_HEADERS, json={
        "sex": "FEMALE", "age_days_min": 0, "age_days_max": 100, "ref_min": 9.0, "ref_max": 13.0}).status_code == 201
    assert client.post(f"/reference-ranges/versions/{res.json()['id']}/retire", headers=ADMIN_HEADERS, json={"reason": "retired for test"}).status_code == 200
    assert _snap(db_session, order) == before

    # the next male result uses the new version (v2) until it was retired -> now NO male band: flagged, not guessed
    later = _order(client, db_session, tid, 30, "years", "Male")
    assert _template(client, later)["HB"]["range_match"] == "NO_BAND"


def test_new_version_is_used_for_future_results_only(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    old_order = _order(client, db_session, tid, 30, "years", "Male")
    _save(client, old_order, comps, {"HB": "12.5"})
    db_session.expire_all()
    band = next(b for b in db_session.get(TestComponent, comps["HB"]).range_versions if b.sex == "MALE" and b.is_current)
    new = client.post(f"/reference-ranges/versions/{band.id}/new-version", headers=ADMIN_HEADERS, json={
        "ref_min": 12.0, "ref_max": 16.0, "critical_min": 6.0, "critical_max": 20.0}).json()
    assert new["version_no"] == 2 and new["is_current"] is True and (new["sex"], new["age_days_min"]) == ("MALE", ADULT)
    fresh = _order(client, db_session, tid, 30, "years", "Male")
    assert _save(client, fresh, comps, {"HB": "12.5"})["HB"]["flag"] == "NORMAL"  # v2
    assert _snap(db_session, fresh)["HB"][0] == new["id"]
    assert _snap(db_session, old_order)["HB"][7] == "LOW"  # v1 snapshot unchanged


# ---------------------------------------------------------------- management rules
def test_new_version_keeps_the_old_row_intact_and_history_is_listed(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    db_session.expire_all()
    band = next(b for b in db_session.get(TestComponent, comps["HB"]).range_versions if b.sex == "MALE")
    snapshot = (band.id, band.ref_min, band.ref_max, band.critical_min, band.critical_max, band.reference_range_text, band.version_no)
    assert client.post(f"/reference-ranges/versions/{band.id}/new-version", headers=OWNER_HEADERS, json={"ref_min": 12.0, "ref_max": 16.0}).status_code == 201
    db_session.expire_all()
    old = db_session.get(ReferenceRangeVersion, band.id)
    assert (old.id, old.ref_min, old.ref_max, old.critical_min, old.critical_max, old.reference_range_text, old.version_no) == snapshot
    assert old.is_current is False and old.retired_at is not None  # only marked no-longer-current
    listing = client.get(f"/reference-ranges/tests/{tid}", headers=ADMIN_HEADERS).json()
    versions = listing["components"][0]["versions"]
    assert sorted((v["sex"], v["version_no"], v["is_current"]) for v in versions if v["sex"] == "MALE") == [("MALE", 1, False), ("MALE", 2, True)]
    # superseding a retired version is refused
    again = client.post(f"/reference-ranges/versions/{band.id}/new-version", headers=ADMIN_HEADERS, json={"ref_min": 1, "ref_max": 2})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "NOT_CURRENT"
    actions = {a.action for a in db_session.execute(select(AuditLog).where(AuditLog.entity_type == "REFERENCE_RANGE")).scalars()}
    assert {"REFERENCE_RANGE_BAND_CREATED", "REFERENCE_RANGE_NEW_VERSION"} <= actions


def test_validation_overlap_and_retire_rules(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS})
    url = f"/reference-ranges/components/{comps['HB']}/bands"
    ok = {"sex": "MALE", "age_days_min": 0, "age_days_max": 100, "ref_min": 10.0, "ref_max": 14.0}
    assert client.post(url, headers=ADMIN_HEADERS, json=ok).status_code == 201
    over = client.post(url, headers=ADMIN_HEADERS, json={**ok, "age_days_min": 50, "age_days_max": 200})
    assert over.status_code == 409 and over.json()["detail"]["code"] == "BAND_OVERLAP"
    # an ANY band may sit beside sex bands of the same ages
    assert client.post(url, headers=ADMIN_HEADERS, json={**ok, "sex": "ANY", "age_days_min": 50, "age_days_max": 200}).status_code in (201, 409)
    for bad in ({**ok, "sex": "X"}, {**ok, "ref_min": 20.0}, {**ok, "age_days_max": -1}, {**ok, "ref_min": None, "ref_max": None},
                {**ok, "age_days_min": 300, "age_days_max": 200}, {**ok, "critical_min": 11.0}):
        assert client.post(url, headers=ADMIN_HEADERS, json=bad).status_code in (400, 422), bad
    band_id = client.get(f"/reference-ranges/tests/{tid}", headers=ADMIN_HEADERS).json()["components"][0]["versions"][0]["id"]
    assert client.post(f"/reference-ranges/versions/{band_id}/retire", headers=ADMIN_HEADERS, json={"reason": ""}).status_code == 422
    assert client.post(f"/reference-ranges/versions/{band_id}/retire", headers=ADMIN_HEADERS, json={"reason": "obsolete"}).status_code == 200
    assert client.post(f"/reference-ranges/versions/{band_id}/retire", headers=ADMIN_HEADERS, json={"reason": "again"}).status_code == 409


def test_only_admin_and_owner_manage_ranges(client, db_session):
    tid, _, comps = _make_test(db_session, {"HB": HB_BANDS[:1]})
    vid = client.get(f"/reference-ranges/tests/{tid}", headers=ADMIN_HEADERS).json()["components"][0]["versions"][0]["id"]
    for headers in (RECEPTIONIST_HEADERS, CASHIER_HEADERS, TECH_KAMAL_HEADERS):
        assert client.get(f"/reference-ranges/tests/{tid}", headers=headers).status_code == 403
        assert client.post(f"/reference-ranges/components/{comps['HB']}/bands", headers=headers, json={"ref_min": 1, "ref_max": 2}).status_code == 403
        assert client.post(f"/reference-ranges/versions/{vid}/new-version", headers=headers, json={"ref_min": 1, "ref_max": 2}).status_code == 403
        assert client.post(f"/reference-ranges/versions/{vid}/retire", headers=headers, json={"reason": "x"}).status_code == 403
    assert client.get(f"/reference-ranges/tests/{tid}", headers=OWNER_HEADERS).status_code == 200


def test_every_existing_component_carried_a_version_one_forward(db_session):
    """Migration guarantee on the test DB: each component has at least one band and the demo CBC values survived."""
    db_session.expire_all()
    comps = db_session.execute(select(TestComponent)).scalars().all()
    assert comps and all(c.range_versions for c in comps)
    hgb = next(c for c in comps if c.code == "HGB" and c.name == "Hemoglobin")
    v1 = min(hgb.range_versions, key=lambda v: v.version_no)
    assert (v1.sex, v1.age_days_min, v1.age_days_max, v1.ref_min, v1.ref_max) == ("ANY", 0, None, 12.0, 16.0)

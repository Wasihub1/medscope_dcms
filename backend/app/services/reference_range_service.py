"""Prompt 14 (D24): reference ranges versioned by sex and age band in days.

- A *band* is (component, sex, age_days_min..age_days_max inclusive; max None = no upper limit).
- Changing a band never edits a row: `new_version` adds version_no + 1 and marks the old row not current.
- Result entry picks a band by sex + total age in days and snapshots the values onto the result item.
- Selection (never a silently wrong band):
    1. current band for the patient's sex whose age span contains the age      -> MATCHED
    2. current 'ANY' band whose age span contains the age                      -> FALLBACK_ANY
    3. nothing fits                                                           -> NO_BAND (flag left empty,
       the row is marked for review; the old single range is NOT used as a guess)
"""
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.timezone import utc_now
from backend.app.models.test import ReferenceRangeVersion, TestComponent
from backend.app.services.audit_service import log_audit_event

SEXES = ("ANY", "MALE", "FEMALE")
MATCHED, FALLBACK_ANY, NO_BAND = "MATCHED", "FALLBACK_ANY", "NO_BAND"


# ---------------------------------------------------------------------------
# Age and sex conversion
# ---------------------------------------------------------------------------
def _shift_back(visit_date: date, years: int = 0, months: int = 0, days: int = 0) -> date:
    """visit_date minus a calendar span (Feb 29 / month-end clamp to the last valid day)."""
    total_months = visit_date.year * 12 + (visit_date.month - 1) - (years * 12 + months)
    y, m = divmod(total_months, 12)
    m += 1
    import calendar
    d = min(visit_date.day, calendar.monthrange(y, m)[1])
    return date(y, m, d).fromordinal(date(y, m, d).toordinal() - days)


def age_to_days(age_value: int, age_unit: Optional[str], visit_date: Optional[date]) -> int:
    """Total age in days at the visit date (B3 3.5). Years and months are calendar spans counted back
    from the visit date (the patient's date of birth is not recorded, only the age entered at the visit);
    days are used as entered. Without a visit date, 365 / 30 day approximations are used."""
    n = max(0, int(age_value or 0))
    unit = (age_unit or "years").strip().lower()
    if unit.startswith("day"):
        return n
    if visit_date is None:
        return n * 30 if unit.startswith("month") else n * 365
    start = _shift_back(visit_date, months=n) if unit.startswith("month") else _shift_back(visit_date, years=n)
    return (visit_date - start).days


def sex_key(gender: Optional[str]) -> Optional[str]:
    """'MALE' / 'FEMALE', or None when the recorded gender is anything else (Other / Unknown):
    only 'ANY' bands can match such a patient."""
    g = (gender or "").strip().upper()
    if g in ("MALE", "M"):
        return "MALE"
    if g in ("FEMALE", "F"):
        return "FEMALE"
    return None


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
def _covers(v: ReferenceRangeVersion, age_days: int) -> bool:
    return v.age_days_min <= age_days and (v.age_days_max is None or age_days <= v.age_days_max)


def current_bands(db: Session, component_id: int) -> List[ReferenceRangeVersion]:
    return list(db.execute(
        select(ReferenceRangeVersion)
        .where(ReferenceRangeVersion.test_component_id == component_id, ReferenceRangeVersion.is_current == True)  # noqa: E712
        .order_by(ReferenceRangeVersion.age_days_min, ReferenceRangeVersion.sex)
    ).scalars().all())


def pick_band(bands: List[ReferenceRangeVersion], sex: Optional[str], age_days: int) -> Tuple[Optional[ReferenceRangeVersion], str]:
    """Pure selection over already-loaded current bands."""
    if sex in ("MALE", "FEMALE"):
        for b in bands:
            if b.sex == sex and _covers(b, age_days):
                return b, MATCHED
    for b in bands:
        if b.sex == "ANY" and _covers(b, age_days):
            # An 'any' band on a component that has no sex-specific bands is simply that component's range;
            # on a sex-dependent component it is a fallback and is labelled as such.
            return b, (FALLBACK_ANY if _has_sex_bands(bands) else MATCHED)
    return None, NO_BAND


def _has_sex_bands(bands: List[ReferenceRangeVersion]) -> bool:
    return any(b.sex != "ANY" for b in bands)


def select_band(db: Session, component_id: int, sex: Optional[str], age_days: int) -> Tuple[Optional[ReferenceRangeVersion], str]:
    return pick_band(current_bands(db, component_id), sex, age_days)


def bands_by_component(db: Session, component_ids: List[int]) -> Dict[int, List[ReferenceRangeVersion]]:
    out: Dict[int, List[ReferenceRangeVersion]] = {cid: [] for cid in component_ids}
    if not component_ids:
        return out
    rows = db.execute(
        select(ReferenceRangeVersion)
        .where(ReferenceRangeVersion.test_component_id.in_(component_ids), ReferenceRangeVersion.is_current == True)  # noqa: E712
        .order_by(ReferenceRangeVersion.age_days_min, ReferenceRangeVersion.sex)
    ).scalars().all()
    for r in rows:
        out[r.test_component_id].append(r)
    return out


# ---------------------------------------------------------------------------
# Management (Admin / Owner). Rows are never edited or deleted.
# ---------------------------------------------------------------------------
def _validate_values(sex, age_min, age_max, ref_min, ref_max, crit_min, crit_max) -> None:
    if sex not in SEXES:
        raise HTTPException(status_code=400, detail="Sex must be ANY, MALE or FEMALE.")
    if age_min is None or age_min < 0:
        raise HTTPException(status_code=400, detail="Age from (days) must be 0 or more.")
    if age_max is not None and age_max < age_min:
        raise HTTPException(status_code=400, detail="Age to (days) cannot be below age from.")
    if ref_min is not None and ref_max is not None and ref_min > ref_max:
        raise HTTPException(status_code=400, detail="Reference minimum cannot be above the maximum.")
    if crit_min is not None and crit_max is not None and crit_min > crit_max:
        raise HTTPException(status_code=400, detail="Critical minimum cannot be above the maximum.")
    if crit_min is not None and ref_min is not None and crit_min > ref_min:
        raise HTTPException(status_code=400, detail="Critical minimum cannot be above the reference minimum.")
    if crit_max is not None and ref_max is not None and crit_max < ref_max:
        raise HTTPException(status_code=400, detail="Critical maximum cannot be below the reference maximum.")
    if ref_min is None and ref_max is None:
        raise HTTPException(status_code=400, detail="Enter at least a reference minimum or maximum.")


def _overlaps(a_min: int, a_max: Optional[int], b_min: int, b_max: Optional[int]) -> bool:
    a_hi = a_max if a_max is not None else float("inf")
    b_hi = b_max if b_max is not None else float("inf")
    return a_min <= b_hi and b_min <= a_hi


def _assert_no_overlap(db: Session, component_id: int, sex: str, age_min: int, age_max: Optional[int], ignore_id: Optional[int]) -> None:
    for b in current_bands(db, component_id):
        if b.id == ignore_id or b.sex != sex:
            continue
        if _overlaps(age_min, age_max, b.age_days_min, b.age_days_max):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                "code": "BAND_OVERLAP",
                "message": f"This age span overlaps the current {sex} band {b.age_days_min}-{b.age_days_max if b.age_days_max is not None else 'no limit'} days. "
                           "Bands for the same sex cannot overlap: make a new version of that band instead, or retire it first.",
            })


def _component(db: Session, tenant_id: str, component_id: int) -> TestComponent:
    comp = db.get(TestComponent, component_id)
    if not comp or comp.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Test component not found.")
    return comp


def _describe(v: ReferenceRangeVersion) -> str:
    span = f"{v.age_days_min}-{v.age_days_max if v.age_days_max is not None else 'no limit'} days"
    return f"{v.sex}, {span}, ref {v.ref_min}..{v.ref_max}, critical {v.critical_min}..{v.critical_max}"


def create_band(db: Session, tenant_id: str, component_id: int, actor_id: int, acting_role: str, *, sex: str, age_days_min: int,
                age_days_max: Optional[int], ref_min, ref_max, critical_min, critical_max, reference_range_text, note) -> ReferenceRangeVersion:
    comp = _component(db, tenant_id, component_id)
    _validate_values(sex, age_days_min, age_days_max, ref_min, ref_max, critical_min, critical_max)
    _assert_no_overlap(db, comp.id, sex, age_days_min, age_days_max, None)
    now = utc_now()
    row = ReferenceRangeVersion(
        tenant_id=tenant_id, test_component_id=comp.id, sex=sex, age_days_min=age_days_min, age_days_max=age_days_max,
        ref_min=ref_min, ref_max=ref_max, critical_min=critical_min, critical_max=critical_max,
        reference_range_text=(reference_range_text or "").strip() or None,
        version_no=1, is_current=True, effective_from=now, created_by_id=actor_id, created_at=now,
        change_note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    log_audit_event(db=db, tenant_id=tenant_id, action="REFERENCE_RANGE_BAND_CREATED", entity_type="REFERENCE_RANGE",
                    entity_id=row.id, acting_role=acting_role, actor_id=actor_id,
                    after_value=f"Component {comp.code} (test {comp.test_id}): {_describe(row)} v1")
    return row


def new_version(db: Session, tenant_id: str, version_id: int, actor_id: int, acting_role: str, *, ref_min, ref_max,
                critical_min, critical_max, reference_range_text, note) -> ReferenceRangeVersion:
    """Adds version_no + 1 for the SAME band (sex and age span stay), supersedes the old row for future results."""
    old = db.get(ReferenceRangeVersion, version_id)
    if not old or old.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Range version not found.")
    if not old.is_current:
        raise HTTPException(status_code=409, detail={"code": "NOT_CURRENT", "message": "Only the current version of a band can be superseded."})
    _validate_values(old.sex, old.age_days_min, old.age_days_max, ref_min, ref_max, critical_min, critical_max)
    now = utc_now()
    old.is_current = False
    old.retired_at = now
    old.retired_by_id = actor_id
    db.flush()  # free the unique 'current band' slot before inserting its successor
    row = ReferenceRangeVersion(
        tenant_id=tenant_id, test_component_id=old.test_component_id, sex=old.sex,
        age_days_min=old.age_days_min, age_days_max=old.age_days_max,
        ref_min=ref_min, ref_max=ref_max, critical_min=critical_min, critical_max=critical_max,
        reference_range_text=(reference_range_text or "").strip() or None,
        version_no=old.version_no + 1, is_current=True, effective_from=now, created_by_id=actor_id, created_at=now,
        change_note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    log_audit_event(db=db, tenant_id=tenant_id, action="REFERENCE_RANGE_NEW_VERSION", entity_type="REFERENCE_RANGE",
                    entity_id=row.id, acting_role=acting_role, actor_id=actor_id,
                    before_value=f"v{old.version_no}: {_describe(old)}", after_value=f"v{row.version_no}: {_describe(row)}")
    return row


def retire_band(db: Session, tenant_id: str, version_id: int, actor_id: int, acting_role: str, reason: str) -> ReferenceRangeVersion:
    old = db.get(ReferenceRangeVersion, version_id)
    if not old or old.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Range version not found.")
    if not old.is_current:
        raise HTTPException(status_code=409, detail={"code": "NOT_CURRENT", "message": "This band version is already retired."})
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="A reason is required to retire a band.")
    old.is_current = False
    old.retired_at = utc_now()
    old.retired_by_id = actor_id
    old.change_note = ((old.change_note + " | ") if old.change_note else "") + f"Retired: {reason.strip()}"[:300]
    old.change_note = old.change_note[:300]
    db.flush()
    log_audit_event(db=db, tenant_id=tenant_id, action="REFERENCE_RANGE_BAND_RETIRED", entity_type="REFERENCE_RANGE",
                    entity_id=old.id, acting_role=acting_role, actor_id=actor_id,
                    before_value=f"v{old.version_no}: {_describe(old)}", after_value=f"Retired. Reason: {reason.strip()}")
    return old


def add_first_version(db: Session, tenant_id: str, comp: TestComponent, *, ref_min, ref_max, critical_min, critical_max,
                      reference_range_text, note: str = "Version 1") -> ReferenceRangeVersion:
    """Used by the demo-component seeding: version 1, sex ANY, whole age range. No audit row (system seed)."""
    now = utc_now()
    row = ReferenceRangeVersion(
        tenant_id=tenant_id, test_component_id=comp.id, sex="ANY", age_days_min=0, age_days_max=None,
        ref_min=ref_min, ref_max=ref_max, critical_min=critical_min, critical_max=critical_max,
        reference_range_text=reference_range_text, version_no=1, is_current=True, effective_from=now,
        created_at=now, change_note=note,
    )
    db.add(row)
    db.flush()
    return row

"""Prompt 14 (D24): Admin / Owner management of reference-range versions (catalog area).
Gated by the existing `test_catalog.manage` key (Admin and Owner by default; not a money key).
Rows are never edited or deleted: a change adds a new version and marks the old one not current."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor
from backend.app.models.test import ReferenceRangeVersion, Test, TestComponent
from backend.app.services import reference_range_service as rrs

router = APIRouter()


class RangeVersionOut(BaseModel):
    id: int
    test_component_id: int
    sex: str
    age_days_min: int
    age_days_max: Optional[int] = None
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    reference_range_text: Optional[str] = None
    version_no: int
    is_current: bool
    effective_from: datetime
    retired_at: Optional[datetime] = None
    change_note: Optional[str] = None


class ComponentRangesOut(BaseModel):
    component_id: int
    code: str
    name: str
    unit: Optional[str] = None
    versions: List[RangeVersionOut] = []  # every version, newest band first; is_current marks the live ones


class TestRangesOut(BaseModel):
    test_id: int
    test_name: str
    components: List[ComponentRangesOut] = []


class BandIn(BaseModel):
    sex: str = Field(default="ANY", description="ANY, MALE or FEMALE")
    age_days_min: int = Field(default=0, ge=0)
    age_days_max: Optional[int] = Field(default=None, ge=0)
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    reference_range_text: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=300)


class NewVersionIn(BaseModel):
    ref_min: Optional[float] = None
    ref_max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    reference_range_text: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=300)


class RetireIn(BaseModel):
    reason: str = Field(min_length=1, max_length=250)


def _out(v: ReferenceRangeVersion) -> RangeVersionOut:
    return RangeVersionOut(
        id=v.id, test_component_id=v.test_component_id, sex=v.sex, age_days_min=v.age_days_min, age_days_max=v.age_days_max,
        ref_min=v.ref_min, ref_max=v.ref_max, critical_min=v.critical_min, critical_max=v.critical_max,
        reference_range_text=v.reference_range_text, version_no=v.version_no, is_current=v.is_current,
        effective_from=v.effective_from, retired_at=v.retired_at, change_note=v.change_note,
    )


@router.get("/tests/{test_id}", response_model=TestRangesOut, summary="Reference-range bands and version history of a test (Admin/Owner)")
def get_test_ranges(
    test_id: int,
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    test = db.get(Test, test_id)
    if not test or test.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="Test not found.")
    comps = db.execute(
        select(TestComponent).where(TestComponent.tenant_id == actor.tenant_id, TestComponent.test_id == test_id)
        .order_by(TestComponent.sort_order, TestComponent.id)
    ).scalars().all()
    out = []
    for c in comps:
        versions = sorted(c.range_versions, key=lambda v: (v.age_days_min, v.sex, -v.version_no))
        out.append(ComponentRangesOut(component_id=c.id, code=c.code, name=c.name, unit=c.unit, versions=[_out(v) for v in versions]))
    return TestRangesOut(test_id=test.id, test_name=test.name, components=out)


@router.post("/components/{component_id}/bands", response_model=RangeVersionOut, status_code=201,
             summary="Add a new band (sex + age span in days) to a component (Admin/Owner)")
def add_band(
    component_id: int,
    data: BandIn,
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    row = rrs.create_band(
        db, actor.tenant_id, component_id, actor.id, actor.role, sex=data.sex.strip().upper(),
        age_days_min=data.age_days_min, age_days_max=data.age_days_max, ref_min=data.ref_min, ref_max=data.ref_max,
        critical_min=data.critical_min, critical_max=data.critical_max,
        reference_range_text=data.reference_range_text, note=data.note,
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/versions/{version_id}/new-version", response_model=RangeVersionOut, status_code=201,
             summary="New version of an existing band: supersedes it for future results only (Admin/Owner)")
def add_version(
    version_id: int,
    data: NewVersionIn,
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    row = rrs.new_version(
        db, actor.tenant_id, version_id, actor.id, actor.role, ref_min=data.ref_min, ref_max=data.ref_max,
        critical_min=data.critical_min, critical_max=data.critical_max,
        reference_range_text=data.reference_range_text, note=data.note,
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/versions/{version_id}/retire", response_model=RangeVersionOut, summary="Retire a band (reason required); old results keep their snapshot (Admin/Owner)")
def retire(
    version_id: int,
    data: RetireIn,
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    row = rrs.retire_band(db, actor.tenant_id, version_id, actor.id, actor.role, data.reason)
    db.commit()
    db.refresh(row)
    return _out(row)

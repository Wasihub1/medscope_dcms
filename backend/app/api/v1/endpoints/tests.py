from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.models.test import Test, TestDestination
from backend.app.schemas.test import TestResponse, TestDestinationResponse

router = APIRouter()


@router.get("", response_model=List[TestResponse], summary="Search and list active diagnostic tests")
def list_tests(
    q: Optional[str] = Query(default="", description="Search by code, name, department, short name"),
    department: Optional[str] = Query(default=None, description="Department filter"),
    limit: int = Query(default=2500, le=10000),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Test)
        .where(Test.tenant_id == actor.tenant_id, Test.active == True)
        .order_by(Test.department, Test.name)
    )
    if department and department != "ALL":
        stmt = stmt.where(Test.department == department)

    if q and q.strip():
        clean_q = q.strip()
        stmt = stmt.where(
            or_(
                Test.code.ilike(f"%{clean_q}%"),
                Test.name.ilike(f"%{clean_q}%"),
                Test.short_name.ilike(f"%{clean_q}%"),
                Test.alternate_names.ilike(f"%{clean_q}%"),
                Test.department.ilike(f"%{clean_q}%"),
            )
        )

    tests = list(db.execute(stmt.limit(limit)).scalars().all())
    return [TestResponse.model_validate(t) for t in tests]


@router.get("/destinations", response_model=List[TestDestinationResponse], summary="List active test assignment destinations")
def list_destinations(
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    stmt = select(TestDestination).where(
        TestDestination.tenant_id == actor.tenant_id,
        TestDestination.active == True,
    ).order_by(TestDestination.destination_type, TestDestination.name)
    dests = list(db.execute(stmt).scalars().all())
    return [TestDestinationResponse.model_validate(d) for d in dests]


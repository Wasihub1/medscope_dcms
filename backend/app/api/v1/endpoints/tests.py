from typing import List, Optional
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.models.test import Test, TestDestination
from backend.app.schemas.test import TestResponse, TestDestinationResponse
from backend.app.schemas.soft_delete import DeleteRequest, DeletedItemResponse, RestoredResponse
from backend.app.services import soft_delete_service as sd

router = APIRouter()


@router.get("", response_model=List[TestResponse], summary="Search and list active diagnostic tests")
def list_tests(
    q: Optional[str] = Query(default="", description="Search by code, name, department, short name"),
    department: Optional[str] = Query(default=None, description="Department filter"),
    limit: int = Query(default=2500, le=10000),
    actor: CurrentActor = Depends(require_permission("test_catalog.view")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Test)
        .where(Test.tenant_id == actor.tenant_id, Test.active == True, Test.deleted_at.is_(None))
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


@router.get("/deleted", response_model=List[DeletedItemResponse], summary="Deleted catalog tests (Prompt 11, Admin/Owner)")
def list_deleted(
    q: Optional[str] = Query(default=""),
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    return sd.list_deleted_tests(db, actor.tenant_id, q)


@router.post("/{test_id}/delete", response_model=DeletedItemResponse, summary="Soft-delete a catalog test (reason required)")
def soft_delete(
    test_id: int,
    data: DeleteRequest = Body(default_factory=DeleteRequest),
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    t = sd.delete_test(db, actor, test_id, data.reason)
    db.commit()
    return DeletedItemResponse(
        id=t.id, kind="TEST", title=f"[{t.code}] {t.name}", subtitle=t.department, deleted_at=t.deleted_at,
        deleted_by_id=t.deleted_by_id, deleted_by_name=sd.staff_names(db, [t.deleted_by_id]).get(t.deleted_by_id),
        delete_reason=t.delete_reason,
    )


@router.post("/{test_id}/restore", response_model=RestoredResponse, summary="Restore a deleted catalog test")
def restore(
    test_id: int,
    actor: CurrentActor = Depends(require_permission("test_catalog.manage")),
    db: Session = Depends(get_db),
):
    t = sd.restore_test(db, actor, test_id)
    db.commit()
    return RestoredResponse(id=t.id, kind="TEST", title=f"[{t.code}] {t.name}", message="Test restored.")


@router.get("/destinations", response_model=List[TestDestinationResponse], summary="List active test assignment destinations")
def list_destinations(
    actor: CurrentActor = Depends(require_permission("test_catalog.view")),
    db: Session = Depends(get_db),
):
    stmt = select(TestDestination).where(
        TestDestination.tenant_id == actor.tenant_id,
        TestDestination.active == True,
    ).order_by(TestDestination.destination_type, TestDestination.name)
    dests = list(db.execute(stmt).scalars().all())
    return [TestDestinationResponse.model_validate(d) for d in dests]


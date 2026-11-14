from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission, has_permission
from backend.app.models.test import TestDestination
from backend.app.models.test_order import AssignmentHistory
from backend.app.schemas.test import TestDestinationResponse
from backend.app.schemas.assignment import (
    AssignedTestOrderResponse,
    UnassignedOrderResponse,
    ManualAssignRequest,
    AssignmentHistoryResponse,
)
from backend.app.services.assignment_service import (
    list_assigned_test_orders,
    list_unassigned_test_orders,
    manually_assign_test_order,
)

router = APIRouter()


class AssignOrderByIdRequest(BaseModel):
    lab_section: Optional[str] = None
    destination_id: Optional[str] = None
    destination_name: Optional[str] = None
    assigned_destination: Optional[str] = None
    notes: Optional[str] = None
    reason: Optional[str] = None


class BulkAssignItem(BaseModel):
    test_order_id: int
    lab_section: Optional[str] = None
    destination_id: Optional[str] = None
    destination_name: Optional[str] = None


class BulkAssignRequest(BaseModel):
    assignments: List[BulkAssignItem]


@router.get("/destinations", response_model=List[TestDestinationResponse], summary="List active test assignment destinations (alias)")
def list_assignment_destinations(
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    stmt = select(TestDestination).where(
        TestDestination.tenant_id == actor.tenant_id,
        TestDestination.active == True,
    ).order_by(TestDestination.destination_type, TestDestination.name)
    dests = list(db.execute(stmt).scalars().all())
    return [TestDestinationResponse.model_validate(d) for d in dests]


@router.get("/unassigned", response_model=List[UnassignedOrderResponse], summary="List unassigned test orders")
def get_unassigned_orders(
    department: Optional[str] = Query(default=None, description="Department filter"),
    limit: int = Query(default=50, le=100),
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    return list_unassigned_test_orders(db, actor.tenant_id, department=department, limit=limit)


@router.get("/orders", response_model=List[AssignedTestOrderResponse], summary="Assigned Tests: every test order with room and technicians (Prompt 10F, money-free)")
def get_assigned_orders(
    status_filter: Optional[str] = Query(default=None, alias="status", description="ALL, OPEN, UNASSIGNED, ASSIGNED, SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, PENDING, COMPLETED, CANCELLED, NOT_PERFORMED"),
    lab_section: Optional[str] = Query(default=None, description="Room code, NONE (no room) or ALL"),
    q: Optional[str] = Query(default=None, description="Search patient, invoice no or test"),
    limit: int = Query(default=200, ge=1, le=500),
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    """View for RECEPTIONIST / CASHIER (view only), ADMIN and OWNER. Moving an order uses the
    existing POST /worklist/{id}/reassign (worklist.reassign); can_reassign is computed here."""
    return list_assigned_test_orders(db, actor.tenant_id, actor, status_filter=status_filter,
                                     lab_section=lab_section, query=q, limit=limit)


@router.post("/assign", response_model=dict, status_code=status.HTTP_200_OK, summary="Manually assign an unassigned test order")
def assign_order(
    data: ManualAssignRequest,
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    order = manually_assign_test_order(
        db=db,
        tenant_id=actor.tenant_id,
        data=data,
        assigner_id=actor.id,
        acting_role=actor.role,
        can_reassign=has_permission(actor, "worklist.reassign"),
    )
    db.commit()
    return {
        "success": True,
        "message": f"Test order #{order.id} successfully assigned to {order.assigned_destination}.",
        "test_order_id": order.id,
        "status": order.status,
    }


@router.post("/{test_order_id}/assign", response_model=dict, status_code=status.HTTP_200_OK, summary="Assign test order by path parameter")
def assign_order_by_path(
    test_order_id: int,
    data: AssignOrderByIdRequest,
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    manual_req = ManualAssignRequest(
        test_order_id=test_order_id,
        lab_section=data.lab_section,
        assigned_destination=data.assigned_destination or data.destination_name or data.destination_id,
        reason=data.reason or data.notes,
    )
    order = manually_assign_test_order(
        db=db,
        tenant_id=actor.tenant_id,
        data=manual_req,
        assigner_id=actor.id,
        acting_role=actor.role,
        can_reassign=has_permission(actor, "worklist.reassign"),
    )
    db.commit()
    return {
        "success": True,
        "message": f"Test order #{order.id} successfully assigned to {order.assigned_destination}.",
        "test_order_id": order.id,
        "status": order.status,
    }


@router.post("/bulk-assign", response_model=dict, status_code=status.HTTP_200_OK, summary="Bulk assign multiple test orders")
def bulk_assign_orders(
    data: BulkAssignRequest,
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    assigned_count = 0
    for item in data.assignments:
        manual_req = ManualAssignRequest(
            test_order_id=int(item.test_order_id),
            lab_section=item.lab_section,
            assigned_destination=item.destination_name or item.destination_id,
        )
        manually_assign_test_order(
            db=db,
            tenant_id=actor.tenant_id,
            data=manual_req,
            assigner_id=actor.id,
            acting_role=actor.role,
            can_reassign=has_permission(actor, "worklist.reassign"),
        )
        assigned_count += 1
    db.commit()
    return {
        "success": True,
        "message": f"{assigned_count} test orders successfully assigned.",
        "assigned_count": assigned_count,
    }


@router.get("/history/{test_order_id}", response_model=List[AssignmentHistoryResponse], summary="View assignment audit history for a test order")
def get_order_history(
    test_order_id: int,
    actor: CurrentActor = Depends(require_permission("assignment.manage")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AssignmentHistory)
        .where(
            AssignmentHistory.tenant_id == actor.tenant_id,
            AssignmentHistory.test_order_id == test_order_id,
        )
        .order_by(desc(AssignmentHistory.changed_at))
    )
    logs = list(db.execute(stmt).scalars().all())
    return [
        AssignmentHistoryResponse(
            id=l.id,
            test_order_id=l.test_order_id,
            previous_assignee=l.previous_assignee,
            new_assignee=l.new_assignee,
            reason=l.reason,
            changed_by_name=l.changed_by.display_name if l.changed_by else None,
            changed_at=l.changed_at,
        )
        for l in logs
    ]


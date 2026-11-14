"""Prompt 15 (D22): doctor sign-off queue and approval. One permission (the existing
result.complete_doctor_routed); Admin/Owner act on a doctor's behalf, a DOCTOR login acts for itself."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor
from backend.app.schemas.doctor_approval import (
    ApprovalDetailResponse, ApprovalQueueItem, ApprovalQueueResponse, ApprovalRecord, ApproveRequest, AssignDoctorRequest,
)
from backend.app.services import doctor_approval_service as svc

router = APIRouter()
_perm = require_permission(svc.APPROVAL_PERMISSION)


@router.get("/queue", response_model=ApprovalQueueResponse, summary="Results awaiting doctor sign-off (DOCTOR: own; Admin/Owner: all, filter by doctor)")
def queue(
    doctor_id: Optional[int] = Query(default=None, description="Admin/Owner: only this doctor's assigned orders"),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    actor: CurrentActor = Depends(_perm),
    db: Session = Depends(get_db),
):
    return svc.list_queue(db, actor, doctor_id, q, limit)


@router.get("/{test_order_id}", response_model=ApprovalDetailResponse, summary="One pending approval: read-only result, rule, doctor, technician sign-off")
def detail(test_order_id: int, actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    return svc.get_detail(db, actor, test_order_id)


@router.post("/{test_order_id}/approve", response_model=ApprovalRecord, status_code=status.HTTP_201_CREATED,
             summary="Record the doctor's approval (Path A: Admin/Owner with attestation; Path B: the DOCTOR themself)")
def approve(test_order_id: int, data: ApproveRequest, actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    rec = svc.approve(db, actor, test_order_id, data)
    db.commit()
    return rec


@router.post("/{test_order_id}/assign-doctor", response_model=ApprovalQueueItem, summary="Put an order in a doctor's queue (Admin/Owner)")
def assign_doctor(test_order_id: int, data: AssignDoctorRequest, actor: CurrentActor = Depends(_perm), db: Session = Depends(get_db)):
    item = svc.assign_doctor(db, actor, test_order_id, data.doctor_id)
    db.commit()
    return item

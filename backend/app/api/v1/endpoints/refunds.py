from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist, require_admin
from backend.app.schemas.refund import (
    RefundEligibilityResponse,
    RefundRequestCreate,
    RefundDisbursementRequest,
    AdminReviewRefundRequest,
    RefundRequestResponse,
)
from backend.app.services.refund_service import (
    check_refund_eligibility,
    initiate_refund_request,
    list_refund_requests,
    admin_review_refund_request,
    disburse_refund,
)

router = APIRouter()


def to_refund_response(req) -> RefundRequestResponse:
    disb_name = req.disbursed_by.display_name if getattr(req, "disbursed_by", None) else None
    rev_name = req.reviewed_by.display_name if getattr(req, "reviewed_by", None) else None
    req_name = req.requested_by.display_name if getattr(req, "requested_by", None) else "Staff"
    return RefundRequestResponse(
        id=req.id,
        invoice_id=req.invoice_id,
        invoice_no=req.invoice.invoice_no if req.invoice else None,
        invoice_line_id=req.invoice_line_id,
        test_name=req.invoice_line.test_name_snapshot if req.invoice_line else None,
        amount=req.amount,
        reason=req.reason,
        request_type=getattr(req, "request_type", "PRE_SAMPLE_CANCELLATION"),
        status=req.status,
        requested_by_id=req.requested_by_id,
        requested_by_name=req_name,
        requested_at=req.requested_at,
        reviewed_by_id=req.reviewed_by_id,
        reviewed_by_name=rev_name,
        reviewed_at=req.reviewed_at,
        review_notes=req.review_notes,
        disbursed_at=req.disbursed_at,
        disbursed_by_id=req.disbursed_by_id,
        disbursed_by_name=disb_name,
        disbursement_method=req.disbursement_method,
        disbursement_reference=req.disbursement_reference,
        invoice_number=req.invoice.invoice_no if req.invoice else None,
        patient_name=req.invoice.patient.name if (req.invoice and req.invoice.patient) else None,
    )


@router.get("/eligibility/{invoice_line_id}", response_model=RefundEligibilityResponse, summary="Check pre-sample refund eligibility for a test line")
def get_eligibility(
    invoice_line_id: int,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return check_refund_eligibility(db, actor.tenant_id, invoice_line_id)


@router.post("/request", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED, summary="Initiate a refund request (Receptionist/Admin)")
@router.post("", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED, summary="Initiate a refund request (alias)")
@router.post("/", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED, summary="Initiate a refund request (alias)")
def request_refund(
    data: RefundRequestCreate,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    req = initiate_refund_request(
        db=db,
        tenant_id=actor.tenant_id,
        data=data,
        requested_by_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(req)
    return to_refund_response(req)


@router.get("/requests", response_model=List[RefundRequestResponse], summary="List refund requests and statuses")
@router.get("", response_model=List[RefundRequestResponse], summary="List refund requests (alias)")
@router.get("/", response_model=List[RefundRequestResponse], summary="List refund requests (alias)")
def get_refund_requests(
    status: Optional[str] = Query(default=None, description="Status filter: PENDING_ADMIN_APPROVAL, APPROVED, REJECTED, DISBURSED"),
    limit: int = Query(default=50, le=100),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    requests = list_refund_requests(db, actor.tenant_id, status_filter=status, limit=limit)
    return [to_refund_response(r) for r in requests]


@router.post("/review/{request_id}", response_model=RefundRequestResponse, summary="Admin approval/rejection endpoint")
@router.post("/{request_id}/review", response_model=RefundRequestResponse, summary="Admin review endpoint (alias)")
def review_refund(
    request_id: int,
    data: AdminReviewRefundRequest,
    admin_actor: CurrentActor = Depends(require_admin),
    db: Session = Depends(get_db),
):
    action = data.action or data.status or "APPROVE"
    notes = data.review_notes or data.rejection_reason
    req = admin_review_refund_request(
        db=db,
        tenant_id=admin_actor.tenant_id,
        request_id=request_id,
        action=action,
        reviewer_id=admin_actor.id,
        review_notes=notes,
        acting_role=admin_actor.role,
    )
    db.commit()
    db.refresh(req)
    return to_refund_response(req)


@router.post("/disburse/{request_id}", response_model=RefundRequestResponse, summary="Disburse approved refund")
@router.post("/{request_id}/disburse", response_model=RefundRequestResponse, summary="Disburse approved refund (alias)")
def disburse_approved_refund(
    request_id: int,
    data: RefundDisbursementRequest,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    req = disburse_refund(
        db=db,
        tenant_id=actor.tenant_id,
        request_id=request_id,
        disburser_id=actor.id,
        data=data,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(req)
    return to_refund_response(req)

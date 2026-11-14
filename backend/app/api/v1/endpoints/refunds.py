from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.schemas.refund import (
    RefundEligibilityResponse,
    RefundRequestCreate,
    RefundDisbursementRequest,
    AdminReviewRefundRequest,
    RefundRequestResponse,
    CancellationBreakdown,
    InvoiceCancellationBreakdown,
    InvoiceCancellationCreate,
)
from fastapi import HTTPException
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.refund import RefundRequest
from backend.app.services.refund_service import (
    cancellation_breakdown,
    cancel_invoice_now,
    invoice_cancellable_lines,
    simulate_invoice_cancellation,
    line_cancellation_blocker,
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
    actor: CurrentActor = Depends(require_permission("refund.view")),
    db: Session = Depends(get_db),
):
    return check_refund_eligibility(db, actor.tenant_id, invoice_line_id)


def _breakdown_response(line, outcome, blocker, request=None) -> CancellationBreakdown:
    return CancellationBreakdown(
        invoice_line_id=line.id,
        test_name=line.test_name_snapshot,
        invoice_total=outcome["invoice_total"],
        paid_total=outcome["paid_total"],
        line_price=outcome["line_price"],
        retained_amount=outcome["retained_amount"],
        refund_amount=outcome["refund_amount"],
        due_after=outcome["due_after"],
        net_after=outcome["net_after"],
        can_request=blocker is None,
        blocker=blocker,
        snapshot_refund_amount=request.amount if request is not None else None,
        differs_from_snapshot=(request.amount != outcome["refund_amount"]) if request is not None else None,
    )


@router.get("/preview/{invoice_line_id}", response_model=CancellationBreakdown, summary="Read-only refund breakdown for cancelling one line now")
def preview_cancellation(
    invoice_line_id: int,
    actor: CurrentActor = Depends(require_permission("refund.request")),
    db: Session = Depends(get_db),
):
    line = db.get(InvoiceLine, invoice_line_id)
    if not line or line.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice line not found.")
    return _breakdown_response(line, cancellation_breakdown(line.invoice, line), line_cancellation_blocker(db, line))


@router.get("/requests/{request_id}/breakdown", response_model=CancellationBreakdown, summary="Approval view: live breakdown beside the request-time snapshot")
def request_breakdown(
    request_id: int,
    actor: CurrentActor = Depends(require_permission("refund.view")),
    db: Session = Depends(get_db),
):
    req = db.get(RefundRequest, request_id)
    if not req or req.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund request not found.")
    line = req.invoice_line
    # While pending, the request itself is excluded from the committed refunds (it is not committed yet).
    outcome = cancellation_breakdown(req.invoice, line, exclude_request_id=req.id)
    return _breakdown_response(line, outcome, None if req.status == "PENDING_ADMIN_APPROVAL" else req.status, req)


@router.get("/preview-invoice/{invoice_id}", response_model=InvoiceCancellationBreakdown, summary="Read-only breakdown for cancelling the whole invoice now (no line locked)")
def preview_invoice_cancellation(
    invoice_id: int,
    actor: CurrentActor = Depends(require_permission("refund.request")),
    db: Session = Depends(get_db),
):
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    try:
        lines = invoice_cancellable_lines(db, inv)
    except HTTPException as exc:
        d = exc.detail
        return InvoiceCancellationBreakdown(
            invoice_id=inv.id, can_cancel=False,
            blocker=d.get("code") if isinstance(d, dict) else "NOT_CONFIRMED",
            blocker_message=d.get("message") if isinstance(d, dict) else str(d),
        )
    return InvoiceCancellationBreakdown(invoice_id=inv.id, can_cancel=True, **simulate_invoice_cancellation(inv, lines))


@router.post("/cancel-invoice", response_model=List[RefundRequestResponse], status_code=status.HTTP_201_CREATED, summary="Cancel every line of an invoice together, no approval step, no payout (only when no line is locked)")
def cancel_whole_invoice(
    data: InvoiceCancellationCreate,
    actor: CurrentActor = Depends(require_permission("refund.request")),
    db: Session = Depends(get_db),
):
    reqs = cancel_invoice_now(
        db=db, tenant_id=actor.tenant_id, invoice_id=data.invoice_id, reason=data.reason,
        actor_id=actor.id, acting_role=actor.role,
    )
    db.commit()
    for r in reqs:
        db.refresh(r)
    return [to_refund_response(r) for r in reqs]


@router.post("/request", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED, summary="Cancel one unlocked test line before the sample is taken, no approval step (Receptionist/Cashier/Admin/Owner)")
@router.post("", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED, summary="Initiate a refund request (alias)")
@router.post("/", response_model=RefundRequestResponse, status_code=status.HTTP_201_CREATED, summary="Initiate a refund request (alias)")
def request_refund(
    data: RefundRequestCreate,
    actor: CurrentActor = Depends(require_permission("refund.request")),
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
    actor: CurrentActor = Depends(require_permission("refund.view")),
    db: Session = Depends(get_db),
):
    requests = list_refund_requests(db, actor.tenant_id, status_filter=status, limit=limit)
    return [to_refund_response(r) for r in requests]


@router.post("/review/{request_id}", response_model=RefundRequestResponse, summary="Admin approval/rejection endpoint")
@router.post("/{request_id}/review", response_model=RefundRequestResponse, summary="Admin review endpoint (alias)")
def review_refund(
    request_id: int,
    data: AdminReviewRefundRequest,
    admin_actor: CurrentActor = Depends(require_permission("refund.approve")),
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
    actor: CurrentActor = Depends(require_permission("refund.disburse")),
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

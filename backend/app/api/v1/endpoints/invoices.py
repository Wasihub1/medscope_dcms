from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.models.invoice import Invoice
from backend.app.models.refund import RefundRequest
from backend.app.schemas.invoice import (
    InvoiceConfirmRequest,
    InvoiceResponse,
    InvoiceDetailResponse,
    InvoiceLineResponse,
)
from backend.app.schemas.payment import PaymentResponse
from backend.app.schemas.patient import PatientResponse
from backend.app.schemas.refund import RefundRequestResponse
from backend.app.services.invoice_service import (
    create_and_confirm_invoice,
    search_invoices,
)
from backend.app.services.audit_service import log_reprint_event

router = APIRouter()


def compute_invoice_refund_status(refund_requests: list, lines: list, refund_due: int) -> str:
    """Computes invoice-level refund status per Prompt 04 Item 14 & Prompt 07 Fix 4."""
    if not refund_requests:
        return "NO_REFUND"
    has_pending = any(r.status == "PENDING_ADMIN_APPROVAL" for r in refund_requests)
    if has_pending:
        return "REFUND_PENDING"
    disbursed_reqs = [r for r in refund_requests if r.status == "DISBURSED"]
    approved_reqs = [r for r in refund_requests if r.status == "APPROVED"]
    all_rejected = all(r.status == "REJECTED" for r in refund_requests)
    if all_rejected:
        return "REFUND_REJECTED"
    if disbursed_reqs:
        active_lines = [l for l in lines if l.status != "CANCELLED"]
        if not active_lines:
            return "FULLY_REFUNDED"
        return "PARTIALLY_REFUNDED"
    if approved_reqs:
        return "REFUND_APPROVED"
    return "NO_REFUND"


@router.post("", response_model=InvoiceDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create and confirm new invoice")
def create_invoice(
    data: InvoiceConfirmRequest,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    inv = create_and_confirm_invoice(
        db=db,
        tenant_id=actor.tenant_id,
        data=data,
        creator_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    return get_invoice_detail(inv.id, actor, db)


@router.get("", response_model=List[InvoiceResponse], summary="Search and list invoices")
def list_invoices(
    q: Optional[str] = Query(default=None, description="Invoice no, patient name, phone, patient code"),
    status: Optional[str] = Query(default=None, description="Payment status filter"),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, le=200),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    invoices = search_invoices(
        db=db,
        tenant_id=actor.tenant_id,
        query=q,
        payment_status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    inv_ids = [inv.id for inv in invoices]
    reqs_by_inv = {}
    if inv_ids:
        refund_reqs = db.execute(
            select(RefundRequest).where(
                RefundRequest.tenant_id == actor.tenant_id,
                RefundRequest.invoice_id.in_(inv_ids),
            )
        ).scalars().all()
        for r in refund_reqs:
            reqs_by_inv.setdefault(r.invoice_id, []).append(r)

    results = []
    for inv in invoices:
        r_status = inv.refund_status if inv.refund_status and inv.refund_status != "NO_REFUND" else compute_invoice_refund_status(reqs_by_inv.get(inv.id, []), inv.lines, inv.refund_due)
        results.append(
            InvoiceResponse(
                id=inv.id,
                invoice_no=inv.invoice_no,
                temp_invoice_id=inv.temp_invoice_id,
                patient_id=inv.patient_id,
                visit_id=inv.visit_id,
                prescribed_by_id=inv.prescribed_by_id,
                prescribed_by_name=inv.prescribed_by.name if inv.prescribed_by else None,
                referrer_id=inv.referrer_id,
                referrer_name=inv.referrer.name if inv.referrer else None,
                status=inv.status,
                payment_status=inv.payment_status,
                refund_status=r_status,
                gross=inv.gross,
                discount=inv.discount,
                net=inv.net,
                paid=inv.paid,
                due=inv.due,
                refund_due=inv.refund_due,
                urgent=inv.urgent,
                created_at=inv.created_at,
                created_by_name=inv.created_by.display_name if inv.created_by else None,
                patient_name=inv.patient.name,
                patient_code=inv.patient.patient_code,
                patient_phone=inv.patient.phone,
            )
        )
    return results


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse, summary="Get invoice detail by ID")
def get_invoice_detail(
    invoice_id: int,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    refund_reqs = db.execute(
        select(RefundRequest).where(
            RefundRequest.tenant_id == actor.tenant_id,
            RefundRequest.invoice_id == inv.id,
        ).order_by(desc(RefundRequest.requested_at))
    ).scalars().all()
    reqs_by_line = {r.invoice_line_id: r for r in refund_reqs}

    line_responses = []
    has_uncollected_line = False
    for line in inv.lines:
        order = line.test_order
        sample = order.sample if order else None
        is_locked = getattr(line, "is_locked", False)
        locked_reason = getattr(line, "locked_reason", None)
        outcome = getattr(order, "outcome", None) if order else None

        # Authoritative sample status (Section 5 Fix 3 & Fix 4)
        if sample:
            s_status = sample.status  # COLLECTED, REJECTED, SPOILED
        elif order and (order.performing_role == "DOCTOR" or (line.test and line.test.requires_doctor)):
            if order.status in ("AWAITING_DOCTOR", "COMPLETED", "IN_PROGRESS"):
                s_status = "PERFORMED"
            else:
                s_status = "Awaiting Exam"
        else:
            s_status = "Awaiting collection"

        r_status = order.report_version.status if order and order.report_version else "Pending"

        # D15 Refund Status for this specific line
        line_req = reqs_by_line.get(line.id)
        d15_status = line_req.status if line_req else None
        d15_reason = (line_req.review_notes or line_req.reason) if line_req else None

        # Fix 4: Line is eligible for ordinary pre-sample cancellation ONLY if unlocked and not collected/rejected/spoiled
        is_eligible_for_pre_sample = (
            not is_locked
            and s_status not in ("COLLECTED", "REJECTED", "SPOILED", "PERFORMED")
            and line.status != "CANCELLED"
        )
        if is_eligible_for_pre_sample:
            has_uncollected_line = True

        line_responses.append(
            InvoiceLineResponse(
                id=line.id,
                test_id=line.test_id,
                test_code_snapshot=line.test_code_snapshot,
                test_name_snapshot=line.test_name_snapshot,
                department_snapshot=line.department_snapshot,
                unit_price_snapshot=line.unit_price_snapshot,
                discount_type=line.discount_type,
                discount_value=line.discount_value,
                discount_amount=line.discount_amount,
                net_price=line.net_price,
                urgent=line.urgent,
                status=line.status,
                created_at=line.created_at,
                sample_status=s_status,
                report_status=r_status,
                sample_collected=bool(s_status == "COLLECTED"),
                is_locked=is_locked,
                locked_reason=locked_reason,
                outcome=outcome,
                d15_refund_status=d15_status,
                d15_refund_reason=d15_reason,
            )
        )

    payment_responses = [
        PaymentResponse(
            id=p.id,
            invoice_id=p.invoice_id,
            amount=p.amount,
            method=p.method,
            reference=p.reference,
            change_amount=p.change_amount,
            received_at=p.received_at,
            received_by_id=p.received_by_id,
            received_by_name=p.received_by.display_name if p.received_by else None,
        )
        for p in inv.payments
    ]

    r_status = compute_invoice_refund_status(refund_reqs, inv.lines, inv.refund_due)

    return InvoiceDetailResponse(
        id=inv.id,
        invoice_no=inv.invoice_no,
        temp_invoice_id=inv.temp_invoice_id,
        patient_id=inv.patient_id,
        visit_id=inv.visit_id,
        prescribed_by_id=inv.prescribed_by_id,
        prescribed_by_name=inv.prescribed_by.name if inv.prescribed_by else None,
        referrer_id=inv.referrer_id,
        referrer_name=inv.referrer.name if inv.referrer else None,
        status=inv.status,
        payment_status=inv.payment_status,
        refund_status=r_status,
        gross=inv.gross,
        discount=inv.discount,
        net=inv.net,
        paid=inv.paid,
        due=inv.due,
        refund_due=inv.refund_due,
        urgent=inv.urgent,
        created_at=inv.created_at,
        created_by_name=inv.created_by.display_name if inv.created_by else None,
        patient_name=inv.patient.name,
        patient_code=inv.patient.patient_code,
        patient_phone=inv.patient.phone,
        patient=PatientResponse.model_validate(inv.patient),
        lines=line_responses,
        payments=payment_responses,
        can_request_refund=has_uncollected_line,
        is_duplicate_reprint=False,
        refund_requests=[RefundRequestResponse.model_validate(r) for r in refund_reqs],
    )


@router.post("/{invoice_id}/reprint", response_model=InvoiceDetailResponse, summary="Register reprint event and get duplicate receipt data")
def reprint_invoice(
    invoice_id: int,
    reason: Optional[str] = Query(default="Patient requested duplicate copy"),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    # Section 2.8 Audit reprint event
    log_reprint_event(
        db=db,
        tenant_id=actor.tenant_id,
        entity_type="INVOICE",
        entity_id=inv.id,
        reprinted_by_id=actor.id,
        reason=reason,
    )
    db.commit()

    detail = get_invoice_detail(invoice_id, actor, db)
    detail.is_duplicate_reprint = True
    detail.reprint_timestamp = datetime.utcnow()
    detail.reprinted_by_name = actor.display_name
    return detail


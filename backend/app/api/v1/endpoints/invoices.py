from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.core.samples import is_imaging_test, requires_sample
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
from backend.app.schemas.soft_delete import DiscardResponse
from backend.app.services.invoice_service import (
    create_and_confirm_invoice,
    save_invoice_draft,
    finalize_invoice_draft,
    discard_invoice_draft,
    search_invoices,
)
from backend.app.services.audit_service import log_reprint_event
from backend.app.services.line_lock_service import unlock_line_same_day
from backend.app.services.refund_service import (
    CANCELLATION_DISPLAY,
    derive_invoice_refund_status,
    latest_requests_by_line,
    line_cancellation_state,
)

router = APIRouter()


@router.post("", response_model=InvoiceDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create and confirm new invoice")
def create_invoice(
    data: InvoiceConfirmRequest,
    actor: CurrentActor = Depends(require_permission("invoice.finalize")),
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


@router.post("/drafts", response_model=InvoiceDetailResponse, status_code=status.HTTP_201_CREATED, summary="Save a new invoice as DRAFT (no operational effect)")
def create_invoice_draft(
    data: InvoiceConfirmRequest,
    actor: CurrentActor = Depends(require_permission("invoice.create")),
    db: Session = Depends(get_db),
):
    inv = save_invoice_draft(db=db, tenant_id=actor.tenant_id, data=data, creator_id=actor.id, acting_role=actor.role)
    db.commit()
    return get_invoice_detail(inv.id, actor, db)


@router.put("/{invoice_id}/draft", response_model=InvoiceDetailResponse, summary="Update a DRAFT invoice (409 once finalized)")
def update_invoice_draft(
    invoice_id: int,
    data: InvoiceConfirmRequest,
    actor: CurrentActor = Depends(require_permission("invoice.create")),
    db: Session = Depends(get_db),
):
    inv = save_invoice_draft(
        db=db, tenant_id=actor.tenant_id, data=data, creator_id=actor.id, acting_role=actor.role, draft_id=invoice_id
    )
    db.commit()
    return get_invoice_detail(inv.id, actor, db)


@router.delete("/{invoice_id}/draft", response_model=DiscardResponse, summary="Discard (permanently delete) a DRAFT invoice")
def discard_draft(
    invoice_id: int,
    actor: CurrentActor = Depends(require_permission("invoice.create")),
    db: Session = Depends(get_db),
):
    inv = discard_invoice_draft(db, actor, invoice_id)
    temp = inv.temp_invoice_id
    db.commit()
    return DiscardResponse(message="Draft discarded.", discarded_invoice_id=invoice_id, temp_invoice_id=temp)


@router.post("/{invoice_id}/finalize", response_model=InvoiceDetailResponse, summary="Finalize a DRAFT invoice (not repeatable)")
def finalize_invoice(
    invoice_id: int,
    data: Optional[InvoiceConfirmRequest] = Body(default=None),
    actor: CurrentActor = Depends(require_permission("invoice.finalize")),
    db: Session = Depends(get_db),
):
    inv = finalize_invoice_draft(
        db=db, tenant_id=actor.tenant_id, invoice_id=invoice_id, creator_id=actor.id, acting_role=actor.role, data=data
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
    actor: CurrentActor = Depends(require_permission("invoice.view")),
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
        r_status = inv.refund_status if inv.refund_status and inv.refund_status != "NO_REFUND" else derive_invoice_refund_status(reqs_by_inv.get(inv.id, []), inv.lines)
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
                finalized_at=inv.finalized_at,
                urgent_fee=getattr(inv, "urgent_fee", 0) or 0,
            )
        )
    return results


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse, summary="Get invoice detail by ID")
def get_invoice_detail(
    invoice_id: int,
    actor: CurrentActor = Depends(require_permission("invoice.view")),
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
    # Prompt 13: the NEWEST request per line (the old dict comprehension over a newest-first list kept
    # the OLDEST, so a rejected-then-resubmitted line showed the stale REJECTED status).
    reqs_by_line = latest_requests_by_line(refund_reqs)

    line_responses = []
    for line in inv.lines:
        order = line.test_order
        sample = order.sample if order else None
        is_locked = getattr(line, "is_locked", False)
        locked_reason = getattr(line, "locked_reason", None)
        outcome = getattr(order, "outcome", None) if order else None

        # Authoritative sample status (Section 5 Fix 3 & Fix 4)
        if sample:
            s_status = sample.status  # COLLECTED, REJECTED, SPOILED
        elif order and is_imaging_test(line.test, order):
            # Prompt 10E Part 2: imaging never needs a sample
            if order.status in ("AWAITING_DOCTOR", "COMPLETED", "IN_PROGRESS"):
                s_status = "PERFORMED"
            else:
                s_status = "Awaiting Exam"
        elif line.test is not None and not requires_sample(line.test, order):
            # Prompt 10F (F4): only an explicit catalog marker ("None", "N/A", "NA", "No sample")
            s_status = "No sample needed"
        elif order and order.status == "COMPLETED":
            # Prompt 10F (F4): legacy order completed under the 10E rule (NULL = no sample) without a
            # sample; shown as such rather than "Awaiting collection". Existing orders are not changed.
            s_status = "Completed without sample"
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
            and s_status not in ("COLLECTED", "REJECTED", "SPOILED")
            and line.status != "CANCELLED"
        )
        cancel_state = line_cancellation_state(line, line_req)
        # Prompt 13: cancellation / refund states take precedence over the (possibly stale) sample label.
        display_status = CANCELLATION_DISPLAY.get(cancel_state, s_status)
        can_request_cancellation = (
            is_eligible_for_pre_sample
            and inv.status == "CONFIRMED"
            and not (line_req is not None and line_req.status == "PENDING_ADMIN_APPROVAL")
        )

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
                cancellation_state=cancel_state,
                display_status=display_status,
                can_request_cancellation=can_request_cancellation,
                line_urgent_fee=getattr(line, "urgent_fee", 0) or 0,
                lab_section=getattr(order, "lab_section", None) if order else None,
            )
        )

    payment_responses = [
        PaymentResponse(
            id=p.id,
            invoice_id=p.invoice_id,
            amount=p.amount,
            method=p.method,
            reference=p.reference,
            channel_detail=getattr(p, "channel_detail", None),
            change_amount=p.change_amount,
            received_at=p.received_at,
            received_by_id=p.received_by_id,
            received_by_name=p.received_by.display_name if p.received_by else None,
        )
        for p in inv.payments
    ]

    r_status = derive_invoice_refund_status(refund_reqs, inv.lines)

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
        can_request_refund=any(l.can_request_cancellation for l in line_responses),
        is_duplicate_reprint=False,
        refund_requests=[RefundRequestResponse.model_validate(r) for r in refund_reqs],
        finalized_at=inv.finalized_at,
        draft_payload=inv.draft_payload if inv.status == "DRAFT" else None,
        urgent_fee=getattr(inv, "urgent_fee", 0) or 0,
        age_value=inv.visit.age_value if inv.visit else None,
        age_unit=inv.visit.age_unit if inv.visit else None,
        visit_gender=inv.visit.gender if inv.visit else None,
    )


@router.post("/lines/{line_id}/unlock", summary="Owner same-day unlock of a locked test line (reason required)")
def unlock_line(
    line_id: int,
    data: dict = Body(default_factory=dict),
    actor: CurrentActor = Depends(require_permission("invoice.line_unlock")),
    db: Session = Depends(get_db),
):
    line = unlock_line_same_day(db, actor, line_id, data.get("reason"))
    db.commit()
    return {"message": "Line unlocked.", "invoice_line_id": line.id, "is_locked": line.is_locked}


@router.post("/{invoice_id}/reprint", response_model=InvoiceDetailResponse, summary="Register reprint event and get duplicate receipt data")
def reprint_invoice(
    invoice_id: int,
    reason: Optional[str] = Query(default="Patient requested duplicate copy"),
    actor: CurrentActor = Depends(require_permission("invoice.reprint")),
    db: Session = Depends(get_db),
):
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if inv.status == "DRAFT":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A DRAFT invoice cannot be printed as a receipt. Finalize it first.")

    # Section 2.8 Audit reprint event
    log_reprint_event(
        db=db,
        tenant_id=actor.tenant_id,
        entity_type="INVOICE",
        entity_id=inv.id,
        actor_id=actor.id,
        acting_role=actor.role,
        reason=reason,
    )
    db.commit()

    detail = get_invoice_detail(invoice_id, actor, db)
    detail.is_duplicate_reprint = True
    detail.reprint_timestamp = datetime.utcnow()
    detail.reprinted_by_name = actor.display_name
    return detail


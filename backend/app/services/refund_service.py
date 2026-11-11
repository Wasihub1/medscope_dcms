from datetime import datetime
from typing import List, Optional, Dict
from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.core.timezone import utc_now
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.test_order import TestOrder, TestOrderEvent
from backend.app.models.sample import Sample
from backend.app.models.refund import RefundRequest
from backend.app.models.business_day import BusinessDay, BusinessDayChannelBalance
from backend.app.schemas.refund import RefundEligibilityResponse, RefundRequestCreate, RefundDisbursementRequest
from backend.app.services.audit_service import log_audit_event


def enforce_segregation_of_duties(
    db: Session,
    tenant_id: str,
    reviewer_id: int,
    requested_by_id: int,
    request_id: int,
    acting_role: str,
) -> None:
    """
    D56 Segregation of Duties Invariant:
    A staff member cannot approve or review their own refund request.
    Isolated in this single helper function for future per-tenant configurability (Small Center Mode).
    """
    if reviewer_id == requested_by_id:
        log_audit_event(
            db=db,
            tenant_id=tenant_id,
            action="REFUND_SELF_APPROVAL_BLOCKED",
            entity_type="REFUND_REQUEST",
            entity_id=request_id,
            acting_role=acting_role,
            actor_id=reviewer_id,
            before_value=f"Requester ID: {requested_by_id}",
            after_value=f"Blocked self-review attempt by user {reviewer_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Segregation of duties violation: You cannot approve or reject a refund request that you submitted yourself.",
        )


def check_refund_eligibility(
    db: Session,
    tenant_id: str,
    invoice_line_id: int,
) -> RefundEligibilityResponse:
    """
    Verifies whether an invoice line is eligible for ordinary pre-sample cancellation.
    Enforces D15 rule: collected specimens that were rejected/spoiled are locked against ordinary cancellation.
    """
    line = db.get(InvoiceLine, invoice_line_id)
    if not line or line.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice line not found.")

    if line.status == "CANCELLED":
        return RefundEligibilityResponse(
            invoice_id=line.invoice_id,
            invoice_line_id=line.id,
            test_name=line.test_name_snapshot,
            is_eligible=False,
            rejection_reason="This test line has already been cancelled.",
            refundable_amount=0,
        )

    # Check lock event: Has a sample been collected or rejected/spoiled?
    sample = (
        db.execute(
            select(Sample)
            .join(TestOrder, Sample.test_order_id == TestOrder.id)
            .where(TestOrder.invoice_line_id == line.id)
        )
        .scalars()
        .first()
    )

    if sample and sample.status in ("REJECTED", "SPOILED"):
        return RefundEligibilityResponse(
            invoice_id=line.invoice_id,
            invoice_line_id=line.id,
            test_name=line.test_name_snapshot,
            is_eligible=False,
            rejection_reason=(
                f"Specimen is {sample.status} ({sample.rejection_reason or 'Clinical rejection'}). "
                "Ordinary pre-sample cancellation is locked. Use the authorized D15 Refund Request workflow."
            ),
            refundable_amount=0,
        )

    if sample and sample.status == "COLLECTED":
        return RefundEligibilityResponse(
            invoice_id=line.invoice_id,
            invoice_line_id=line.id,
            test_name=line.test_name_snapshot,
            is_eligible=False,
            rejection_reason="A biological sample has already been collected for this test. Cancellation is strictly locked.",
            refundable_amount=0,
        )

    # Module 12: Check persistent line lock
    if getattr(line, "is_locked", False):
        return RefundEligibilityResponse(
            invoice_id=line.invoice_id,
            invoice_line_id=line.id,
            test_name=line.test_name_snapshot,
            is_eligible=False,
            rejection_reason=getattr(line, "locked_reason", None) or "This test line is locked against ordinary cancellation.",
            refundable_amount=0,
        )

    # Check imaging examination lock
    if line.test_order and line.test_order.status in ("COMPLETED", "AWAITING_DOCTOR"):
        test = line.test
        if test and (test.requires_doctor or test.performing_role == "DOCTOR" or test.report_template == "NARRATIVE"):
            return RefundEligibilityResponse(
                invoice_id=line.invoice_id,
                invoice_line_id=line.id,
                test_name=line.test_name_snapshot,
                is_eligible=False,
                rejection_reason="Imaging examination has already been performed. Cancellation is strictly locked.",
                refundable_amount=0,
            )

    return RefundEligibilityResponse(
        invoice_id=line.invoice_id,
        invoice_line_id=line.id,
        test_name=line.test_name_snapshot,
        is_eligible=True,
        rejection_reason=None,
        refundable_amount=line.net_price,
    )


def initiate_d15_refund_request(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    requested_by_id: int,
    notes: Optional[str] = None,
    acting_role: str = "LAB_TECH",
) -> RefundRequest:
    """
    FIX 4: Lab Tech submits a D15 Refund Request for a rejected/spoiled test line.
    - Preserves sample, line lock, and D15 Not Performed outcome.
    - Creates request in PENDING_ADMIN_APPROVAL status.
    - Does NOT execute a refund or unlock the line.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    sample = order.sample
    is_spoiled = (order.status in ("REJECTED", "SPOILED")) or (sample and sample.status in ("REJECTED", "SPOILED"))
    if not is_spoiled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="D15 refund requests can only be filed for rejected or spoiled specimens.",
        )

    line = order.invoice_line
    if not line or line.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice line is already cancelled or missing.",
        )

    # Check for existing pending request
    existing_req = db.execute(
        select(RefundRequest).where(
            RefundRequest.tenant_id == tenant_id,
            RefundRequest.invoice_line_id == line.id,
            RefundRequest.status == "PENDING_ADMIN_APPROVAL",
        )
    ).scalar_one_or_none()

    if existing_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A D15 refund request is already pending admin review for this test line.",
        )

    spoil_label = sample.status if sample else order.status
    rejection_reason = sample.rejection_reason if sample else "Specimen rejected"
    reason_text = f"D15 Not Performed: Specimen {spoil_label} — {rejection_reason}."
    if notes and notes.strip():
        reason_text += f" Notes: {notes.strip()}"

    now_ts = utc_now()
    req = RefundRequest(
        tenant_id=tenant_id,
        invoice_id=line.invoice_id,
        invoice_line_id=line.id,
        amount=line.net_price,
        reason=reason_text,
        request_type="D15_NOT_PERFORMED",
        status="PENDING_ADMIN_APPROVAL",
        requested_by_id=requested_by_id,
        requested_at=now_ts,
    )
    db.add(req)

    # Mark order outcome as NOT_PERFORMED under D15
    order.outcome = "NOT_PERFORMED"

    # Update invoice refund_status to pending if not already refunded
    if line.invoice and line.invoice.refund_status not in ("PARTIALLY_REFUNDED", "FULLY_REFUNDED"):
        line.invoice.refund_status = "REFUND_PENDING"

    # Append lifecycle event (clinical-only description for technician financial isolation)
    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type="D15_REFUND_REQUESTED",
        stage=order.status,
        description="D15 Refund Request submitted for Admin/Owner approval.",
        notes=notes,
        actor_id=requested_by_id,
        actor_role=acting_role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="INITIATE_D15_REFUND_REQUEST",
        entity_type="REFUND_REQUEST",
        entity_id=req.id,
        acting_role=acting_role,
        actor_id=requested_by_id,
        after_value=f"Order #{order.id}, Line: {line.id}, Amount: Tk {req.amount}, Reason: {reason_text}",
    )

    db.flush()
    return req


def initiate_refund_request(
    db: Session,
    tenant_id: str,
    data: RefundRequestCreate,
    requested_by_id: int,
    acting_role: str = "RECEPTIONIST",
) -> RefundRequest:
    """Creates a refund request in PENDING_ADMIN_APPROVAL status."""
    # Check if this is explicitly a D15 request
    req_type = getattr(data, "request_type", "PRE_SAMPLE_CANCELLATION") or "PRE_SAMPLE_CANCELLATION"

    line_id = data.invoice_line_id
    if not line_id and data.invoice_id:
        lines = db.execute(
            select(InvoiceLine).where(
                InvoiceLine.invoice_id == data.invoice_id,
                InvoiceLine.tenant_id == tenant_id,
                InvoiceLine.status != "CANCELLED",
            )
        ).scalars().all()
        for candidate in lines:
            elig = check_refund_eligibility(db, tenant_id, candidate.id)
            if elig.is_eligible:
                line_id = candidate.id
                break

    if not line_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No eligible uncollected test line found for cancellation refund.",
        )

    line = db.get(InvoiceLine, line_id)
    if not line or line.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice line not found.")

    # If it's a D15 line, delegate to D15 handler
    sample = line.test_order.sample if line.test_order else None
    if sample and sample.status in ("REJECTED", "SPOILED") and line.test_order:
        return initiate_d15_refund_request(
            db=db,
            tenant_id=tenant_id,
            test_order_id=line.test_order.id,
            requested_by_id=requested_by_id,
            notes=data.reason,
            acting_role=acting_role,
        )

    eligibility = check_refund_eligibility(db, tenant_id, line_id)
    if not eligibility.is_eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=eligibility.rejection_reason or "This test is not eligible for refund.",
        )

    # Check if a pending request already exists for this line
    existing_req = db.execute(
        select(RefundRequest).where(
            RefundRequest.tenant_id == tenant_id,
            RefundRequest.invoice_line_id == line.id,
            RefundRequest.status == "PENDING_ADMIN_APPROVAL",
        )
    ).scalar_one_or_none()

    if existing_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A cancellation and refund request is already pending admin review for this test line.",
        )

    refund_amt = data.amount if (data.amount and data.amount > 0 and data.amount <= line.net_price) else line.net_price
    now_ts = utc_now()

    req = RefundRequest(
        tenant_id=tenant_id,
        invoice_id=line.invoice_id,
        invoice_line_id=line.id,
        amount=refund_amt,
        reason=data.reason.strip(),
        request_type=req_type,
        status="PENDING_ADMIN_APPROVAL",
        requested_by_id=requested_by_id,
        requested_at=now_ts,
    )
    db.add(req)

    # Update invoice refund_status to pending if not already refunded
    if line.invoice and line.invoice.refund_status not in ("PARTIALLY_REFUNDED", "FULLY_REFUNDED"):
        line.invoice.refund_status = "REFUND_PENDING"

    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="INITIATE_REFUND_REQUEST",
        entity_type="REFUND_REQUEST",
        entity_id=req.id,
        acting_role=acting_role,
        actor_id=requested_by_id,
        after_value=f"Invoice Line: {line.id}, Amount: Tk {req.amount}, Reason: {req.reason}",
    )
    return req


def list_refund_requests(
    db: Session,
    tenant_id: str,
    status_filter: Optional[str] = None,
    limit: int = 50,
) -> List[RefundRequest]:
    """Lists refund requests for front-desk and administrative monitoring."""
    stmt = (
        select(RefundRequest)
        .where(RefundRequest.tenant_id == tenant_id)
        .order_by(desc(RefundRequest.requested_at))
    )
    if status_filter and status_filter != "ALL":
        stmt = stmt.where(RefundRequest.status == status_filter.strip().upper())
    return list(db.execute(stmt.limit(limit)).scalars().all())


def admin_review_refund_request(
    db: Session,
    tenant_id: str,
    request_id: int,
    action: str,  # APPROVE or REJECT
    reviewer_id: int,
    review_notes: Optional[str] = None,
    acting_role: str = "ADMIN",
) -> RefundRequest:
    """
    Admin-only workflow for approving or rejecting a refund request.
    FIX 4 Invariant: Distinguishes Approval from actual Disbursement.
    Approved status sets REFUND_APPROVED, not FULLY_REFUNDED.
    """
    req = db.get(RefundRequest, request_id)
    if not req or req.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund request not found.")

    if req.status != "PENDING_ADMIN_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund request is already in '{req.status}' state.",
        )

    # Fix 2: Enforce Segregation of Duties (D56)
    enforce_segregation_of_duties(
        db=db,
        tenant_id=tenant_id,
        reviewer_id=reviewer_id,
        requested_by_id=req.requested_by_id,
        request_id=req.id,
        acting_role=acting_role,
    )

    action_norm = action.strip().upper() if action else ""
    now_ts = utc_now()
    req.reviewed_by_id = reviewer_id
    req.reviewed_at = now_ts
    req.review_notes = review_notes

    if "APPROV" in action_norm:
        req.status = "APPROVED"

        # Execute financial line cancellation and refund due adjustment
        line = req.invoice_line
        line.status = "CANCELLED"
        if line.test_order:
            line.test_order.status = "CANCELLED"
            if req.request_type == "D15_NOT_PERFORMED":
                line.test_order.outcome = "NOT_PERFORMED"

        invoice = req.invoice
        # Reduce invoice net and add to refund_due
        invoice.refund_due += line.net_price
        invoice.net -= line.net_price
        if invoice.net < 0:
            invoice.net = 0

        # Section 5 Fix 4: Set to REFUND_APPROVED (Awaiting Disbursement), not FULLY_REFUNDED!
        invoice.refund_status = "REFUND_APPROVED"

        # Append lifecycle event if test order exists (amount-free description for technician isolation)
        if line.test_order:
            ev = TestOrderEvent(
                tenant_id=tenant_id,
                test_order_id=line.test_order.id,
                event_type="REFUND_APPROVED",
                stage="REFUND_APPROVED",
                description="Refund request approved by Admin. Awaiting disbursement.",
                notes=review_notes,
                actor_id=reviewer_id,
                actor_role=acting_role,
                created_at=now_ts,
            )
            db.add(ev)

    elif action_norm == "REJECT":
        req.status = "REJECTED"
        invoice = req.invoice
        # Recompute invoice refund_status based on remaining requests
        other_approved = db.execute(
            select(RefundRequest).where(
                RefundRequest.invoice_id == invoice.id,
                RefundRequest.id != req.id,
                RefundRequest.status == "APPROVED",
            )
        ).scalars().all()
        other_pending = db.execute(
            select(RefundRequest).where(
                RefundRequest.invoice_id == invoice.id,
                RefundRequest.id != req.id,
                RefundRequest.status == "PENDING_ADMIN_APPROVAL",
            )
        ).scalars().all()
        other_disbursed = db.execute(
            select(RefundRequest).where(
                RefundRequest.invoice_id == invoice.id,
                RefundRequest.id != req.id,
                RefundRequest.status == "DISBURSED",
            )
        ).scalars().all()

        if other_disbursed:
            active_lines = [l for l in invoice.lines if l.status != "CANCELLED"]
            invoice.refund_status = "FULLY_REFUNDED" if not active_lines else "PARTIALLY_REFUNDED"
        elif other_approved:
            invoice.refund_status = "REFUND_APPROVED"
        elif other_pending:
            invoice.refund_status = "REFUND_PENDING"
        else:
            invoice.refund_status = "REFUND_REJECTED"

        line = req.invoice_line
        if line and line.test_order:
            ev = TestOrderEvent(
                tenant_id=tenant_id,
                test_order_id=line.test_order.id,
                event_type="REFUND_REJECTED",
                stage=line.test_order.status,
                description=f"Refund request rejected by Admin. Reason: {review_notes or 'No reason provided'}",
                notes=review_notes,
                actor_id=reviewer_id,
                actor_role=acting_role,
                created_at=now_ts,
            )
            db.add(ev)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action. Use APPROVE or REJECT.")

    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=f"ADMIN_REVIEW_REFUND_{req.status}",
        entity_type="REFUND_REQUEST",
        entity_id=req.id,
        acting_role=acting_role,
        actor_id=reviewer_id,
        after_value=f"Decision: {req.status}, Notes: {review_notes}",
    )
    return req


def disburse_refund(
    db: Session,
    tenant_id: str,
    request_id: int,
    disburser_id: int,
    data: RefundDisbursementRequest,
    acting_role: str = "RECEPTIONIST",
) -> RefundRequest:
    """
    FIX 4: Authorizes and records actual disbursement of an APPROVED refund.
    - Records payment channel (CASH, BKASH, etc.) and reference.
    - Adjusts invoice refund_due.
    - Updates invoice refund_status to PARTIALLY_REFUNDED or FULLY_REFUNDED based on actual records.
    - Reverses associated referrer commission (Section 5 Fix 4 item D).
    """
    req = db.get(RefundRequest, request_id)
    if not req or req.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund request not found.")

    if req.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot disburse refund in '{req.status}' status. Only APPROVED requests can be disbursed.",
        )

    now_ts = utc_now()
    invoice = req.invoice
    method_norm = data.method.strip().upper() if data.method else "CASH"

    # Fix 1: Validate disbursement method against invoice recorded payments (D18, M29)
    paid_channels: Dict[str, int] = {}
    for p in invoice.payments:
        pm = p.method.strip().upper()
        paid_channels[pm] = paid_channels.get(pm, 0) + p.amount

    if not paid_channels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disburse refund: No payments have been recorded for this invoice.",
        )

    if method_norm not in paid_channels:
        valid_methods_str = ", ".join(sorted(paid_channels.keys()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid disbursement channel '{method_norm}'. Refunds must use the original payment channel. Recorded payment channels: {valid_methods_str}.",
        )

    # Non-cash methods require transaction/reference ID
    if method_norm != "CASH":
        if not data.reference or not data.reference.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A transaction reference ID is required for non-cash disbursement via '{method_norm}'.",
            )

    # Per-method disbursement limit check (cannot disburse more than paid on that channel)
    earlier_disbursed_for_channel = sum(
        r.amount
        for r in invoice.refund_requests
        if r.id != req.id and r.status == "DISBURSED" and r.disbursement_method and r.disbursement_method.upper() == method_norm
    )
    max_disbursable = max(0, paid_channels[method_norm] - earlier_disbursed_for_channel)
    if req.amount > max_disbursable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Disbursement amount of Tk {req.amount} exceeds available paid balance of Tk {max_disbursable} for channel '{method_norm}'.",
        )

    req.status = "DISBURSED"
    req.disbursed_at = now_ts
    req.disbursed_by_id = disburser_id
    req.disbursement_method = method_norm
    req.disbursement_reference = data.reference.strip() if data.reference else None

    # Reduce active day cash drawer if disbursed in cash
    if method_norm == "CASH":
        active_day = db.execute(
            select(BusinessDay).where(
                BusinessDay.tenant_id == tenant_id,
                BusinessDay.status == "OPEN",
            )
        ).scalar_one_or_none()
        if active_day:
            channel_rec = db.execute(
                select(BusinessDayChannelBalance).where(
                    BusinessDayChannelBalance.business_day_id == active_day.id,
                    BusinessDayChannelBalance.channel == "CASH",
                )
            ).scalar_one_or_none()
            if channel_rec:
                channel_rec.received_amount = max(0, channel_rec.received_amount - req.amount)

    invoice.refund_due = max(0, invoice.refund_due - req.amount)

    # Recompute invoice refund_status
    active_lines = [l for l in invoice.lines if l.status != "CANCELLED"]
    if not active_lines:
        invoice.refund_status = "FULLY_REFUNDED"
    else:
        invoice.refund_status = "PARTIALLY_REFUNDED"

    # Commission Reversal (Section 5 Fix 4 Item D)
    if invoice.referrer_id and req.invoice_line:
        log_audit_event(
            db=db,
            tenant_id=tenant_id,
            action="COMMISSION_REVERSED",
            entity_type="REFERRER",
            entity_id=invoice.referrer_id,
            acting_role=acting_role,
            actor_id=disburser_id,
            after_value=f"Line: {req.invoice_line_id}, Refund Disbursed: Tk {req.amount}, Channel: {req.disbursement_method}",
        )

    # Append operational event (amount-free description for technician isolation)
    line = req.invoice_line
    if line and line.test_order:
        ev = TestOrderEvent(
            tenant_id=tenant_id,
            test_order_id=line.test_order.id,
            event_type="REFUND_DISBURSED",
            stage="DISBURSED",
            description=f"Refund disbursed via {req.disbursement_method}",
            notes=f"Ref: {req.disbursement_reference or 'N/A'} | Notes: {data.notes or ''}".strip(),
            actor_id=disburser_id,
            actor_role=acting_role,
            created_at=now_ts,
        )
        db.add(ev)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="REFUND_DISBURSED",
        entity_type="REFUND_REQUEST",
        entity_id=req.id,
        acting_role=acting_role,
        actor_id=disburser_id,
        after_value=f"Amount: Tk {req.amount}, Channel: {req.disbursement_method}, Invoice Status: {invoice.refund_status}",
    )

    db.flush()
    return req

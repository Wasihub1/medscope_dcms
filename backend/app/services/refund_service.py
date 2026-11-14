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
from backend.app.core.payment_channels import normalize_channel
from backend.app.services import accounting_service


# ---------------------------------------------------------------------------
# Prompt 10E Part 1: refund rule on line cancellation (replaces the 10D proportional
# allocation, ADL-036 and assumptions A4/A6). Owner-confirmed rule, whole taka:
#   net_after     = invoice net after removing the cancelled line's net price
#                   (never below the invoice urgent fee: the fee belongs to the invoice
#                   and is not refunded when a line is cancelled)
#   retained_paid = invoice paid - all APPROVED and DISBURSED refunds so far
#   refund_amount = max(0, retained_paid - net_after)
#   due           = max(0, net_after - (retained_paid - refund_amount))
# A refund and a due never coexist after a cancellation, and the sum of all refunds can
# never exceed total paid. Client-supplied refund amounts are never trusted.
# ---------------------------------------------------------------------------
# Refund request statuses whose amount is committed against the invoice's paid money.
COMMITTED_REFUND_STATUSES = ("APPROVED", "DISBURSED")
# A zero-amount approval has nothing to pay out; it is closed immediately with this status.
ZERO_REFUND_CLOSED_STATUS = "COMPLETED"


def _committed_refund_total(invoice: Invoice, exclude_request_id: Optional[int] = None) -> int:
    return sum(
        max(0, r.amount or 0)
        for r in invoice.refund_requests
        if r.status in COMMITTED_REFUND_STATUSES and r.id != exclude_request_id
    )


def compute_cancellation_outcome(
    invoice: Invoice,
    line: InvoiceLine,
    exclude_request_id: Optional[int] = None,
) -> Dict[str, int]:
    """Pure calculation of the Prompt 10E refund rule for cancelling `line` now.
    Returns net_after, retained_paid, refund_amount and due_after (all whole taka, >= 0)."""
    fee_floor = max(0, getattr(invoice, "urgent_fee", 0) or 0)
    net_after = max(fee_floor, max(0, invoice.net) - max(0, line.net_price))
    retained_paid = max(0, invoice.paid - _committed_refund_total(invoice, exclude_request_id))
    refund_amount = max(0, retained_paid - net_after)
    # Prompt 17: money already written off as bad debt is not owed again after a cancellation
    due_after = max(0, net_after - (retained_paid - refund_amount) - max(0, getattr(invoice, "written_off", 0) or 0))
    return {
        # Prompt 13: the read-only breakdown shown by the request / approval modals comes from this
        # same dict (one calculation, no second implementation of the arithmetic).
        "invoice_total": max(0, invoice.net),
        "paid_total": max(0, invoice.paid),
        "line_price": max(0, line.net_price),
        "net_after": net_after,
        "retained_paid": retained_paid,
        "retained_amount": retained_paid - refund_amount,
        "refund_amount": refund_amount,
        "due_after": due_after,
    }


def compute_line_refundable_amount(
    invoice: Invoice,
    line: InvoiceLine,
    exclude_request_id: Optional[int] = None,
) -> int:
    """Refund that cancelling this line would produce right now (Prompt 10E rule)."""
    return compute_cancellation_outcome(invoice, line, exclude_request_id)["refund_amount"]


def _apply_line_cancellation(invoice: Invoice, outcome: Dict[str, int]) -> None:
    """Keeps net / due / payment_status consistent after a line is cancelled."""
    invoice.net = outcome["net_after"]
    invoice.due = outcome["due_after"]
    # Payment status follows money received (paid) and money still owed (due).
    if invoice.paid <= 0:
        invoice.payment_status = "UNPAID"
    elif invoice.due == 0:
        invoice.payment_status = "PAID"
    else:
        invoice.payment_status = "PARTLY_PAID"


def derive_invoice_refund_status(reqs, lines) -> str:
    """Pure derivation of an invoice's refund status from its refund requests and lines.
    Prompt 13: the one implementation (the invoice endpoint used to carry a duplicate)."""
    reqs = list(reqs)
    active_lines = [l for l in lines if l.status != "CANCELLED"]
    if any(r.status == "PENDING_ADMIN_APPROVAL" for r in reqs):
        return "REFUND_PENDING"
    if any(r.status == "APPROVED" and (r.amount or 0) > 0 for r in reqs):
        return "REFUND_APPROVED"
    if any(r.status == "DISBURSED" for r in reqs):
        return "FULLY_REFUNDED" if not active_lines else "PARTIALLY_REFUNDED"
    if reqs and all(r.status == "REJECTED" for r in reqs):
        return "REFUND_REJECTED"
    # No money refunded (e.g. only zero-amount cancellations)
    return "NO_REFUND"


def recompute_invoice_refund_status(invoice: Invoice) -> str:
    """Derives and stores invoice.refund_status from its refund requests."""
    result = derive_invoice_refund_status(invoice.refund_requests, invoice.lines)
    invoice.refund_status = result
    return result


# ---------------------------------------------------------------------------
# Prompt 13: explicit line cancellation state (derived from the line + its newest refund request,
# no new column). Cancellation / refund states take precedence over the sample-status label.
#   NONE                    normal line (a REJECTED request leaves the line normal)
#   CANCELLATION_REQUESTED  request pending Admin/Owner approval
#   CANCELLED_REFUND_PENDING approved, refund awaiting payout
#   CANCELLED               cancelled, nothing to refund
#   CANCELLED_REFUNDED      cancelled and the refund has been paid out
# ---------------------------------------------------------------------------
CANCELLATION_DISPLAY = {
    "CANCELLATION_REQUESTED": "CANCELLATION REQUESTED",
    "CANCELLED_REFUND_PENDING": "CANCELLED - REFUND PENDING PAYOUT",
    "CANCELLED": "CANCELLED",
    "CANCELLED_REFUNDED": "CANCELLED - REFUNDED",
}


def line_cancellation_state(line: InvoiceLine, latest_request: Optional[RefundRequest]) -> str:
    st = latest_request.status if latest_request is not None else None
    if st == "PENDING_ADMIN_APPROVAL":
        return "CANCELLATION_REQUESTED"
    if line.status == "CANCELLED":
        if st == "DISBURSED":
            return "CANCELLED_REFUNDED"
        if st == "APPROVED":
            return "CANCELLED_REFUND_PENDING"
        return "CANCELLED"
    return "NONE"


def latest_requests_by_line(refund_requests) -> Dict[int, RefundRequest]:
    """Newest refund request per invoice line (ties broken by id)."""
    out: Dict[int, RefundRequest] = {}
    for r in sorted(refund_requests, key=lambda r: (r.requested_at, r.id)):
        out[r.invoice_line_id] = r
    return out


def line_lock_blocker(db: Session, line: InvoiceLine) -> Optional[str]:
    """SAMPLE_ALREADY_TAKEN when the line is past its lock event (sample taken / rejected / spoiled,
    or the Prompt 12 result-completion lock); otherwise None. The one lock check for cancellation."""
    if getattr(line, "is_locked", False):
        return "SAMPLE_ALREADY_TAKEN"
    sample = (
        db.execute(
            select(Sample).join(TestOrder, Sample.test_order_id == TestOrder.id)
            .where(TestOrder.invoice_line_id == line.id)
        ).scalars().first()
    )
    if sample and sample.status in ("COLLECTED", "REJECTED", "SPOILED"):
        return "SAMPLE_ALREADY_TAKEN"
    return None


def line_cancellation_blocker(db: Session, line: InvoiceLine) -> Optional[str]:
    """Why this line cannot take a pre-lock cancellation request right now:
    None (it can), ALREADY_CANCELLED, REQUEST_PENDING or SAMPLE_ALREADY_TAKEN."""
    if line.status == "CANCELLED":
        return "ALREADY_CANCELLED"
    pending = db.execute(
        select(RefundRequest.id).where(
            RefundRequest.invoice_line_id == line.id, RefundRequest.status == "PENDING_ADMIN_APPROVAL"
        )
    ).first()
    if pending:
        return "REQUEST_PENDING"
    return line_lock_blocker(db, line)


SAMPLE_TAKEN_MESSAGE = (
    "Sample already taken for this test. It can no longer be cancelled here; cancellation now needs the "
    "Admin/Owner 'Not Performed' (D15) approval path. Please inform Admin/Owner."
)


def cancellation_breakdown(invoice: Invoice, line: InvoiceLine, exclude_request_id: Optional[int] = None) -> Dict[str, int]:
    """Alias used by the preview endpoints: the read-only numbers for cancelling `line` now."""
    return compute_cancellation_outcome(invoice, line, exclude_request_id)


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
    """Whether a line can take a pre-lock cancellation request now (same checks as the request itself)."""
    line = db.get(InvoiceLine, invoice_line_id)
    if not line or line.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice line not found.")

    blocker = line_cancellation_blocker(db, line)
    if blocker is None:
        return RefundEligibilityResponse(
            invoice_id=line.invoice_id, invoice_line_id=line.id, test_name=line.test_name_snapshot,
            is_eligible=True, rejection_reason=None,
            refundable_amount=compute_line_refundable_amount(line.invoice, line),
        )
    reasons = {
        "ALREADY_CANCELLED": "This test line has already been cancelled.",
        "REQUEST_PENDING": "A cancellation request is already pending Admin/Owner approval for this test line.",
        "SAMPLE_ALREADY_TAKEN": (getattr(line, "locked_reason", None) or SAMPLE_TAKEN_MESSAGE)
        if getattr(line, "is_locked", False) else SAMPLE_TAKEN_MESSAGE,
    }
    return RefundEligibilityResponse(
        invoice_id=line.invoice_id, invoice_line_id=line.id, test_name=line.test_name_snapshot,
        is_eligible=False, rejection_reason=reasons[blocker], refundable_amount=0, reason_code=blocker,
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
        amount=compute_line_refundable_amount(line.invoice, line),
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
        after_value=f"Order #{order.id}, Line: {line.id}, Requested refundable amount (capped at paid), Reason: {reason_text}",
    )

    db.flush()
    return req


NO_APPROVAL_NOTE = "No approval step: pre-lock cancellation (sample not taken, no money or stock consumed)."


def _blocker_error(blocker: str) -> HTTPException:
    messages = {
        "SAMPLE_ALREADY_TAKEN": SAMPLE_TAKEN_MESSAGE,
        "REQUEST_PENDING": "A cancellation request is already pending Admin/Owner approval for this test line.",
        "ALREADY_CANCELLED": "This test line has already been cancelled.",
    }
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": blocker, "message": messages[blocker]})


def _cancel_line_now(
    db: Session,
    tenant_id: str,
    line: InvoiceLine,
    actor_id: int,
    acting_role: str,
    reason: str,
    scope: str,
) -> RefundRequest:
    """Prompt 13A: executes one pre-lock line cancellation immediately (no approval step).
    The amount comes from compute_cancellation_outcome (the one calculation). The RefundRequest row is
    kept as the record: APPROVED (refund to pay out) or COMPLETED (nothing to pay). The caller holds the
    row lock, has verified the line is cancellable, and commits once."""
    invoice = line.invoice
    outcome = compute_cancellation_outcome(invoice, line)
    net_before = invoice.net
    now_ts = utc_now()
    req = RefundRequest(
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        invoice_line_id=line.id,
        amount=outcome["refund_amount"],
        reason=reason,
        request_type="PRE_SAMPLE_CANCELLATION",
        status="APPROVED" if outcome["refund_amount"] > 0 else ZERO_REFUND_CLOSED_STATUS,
        requested_by_id=actor_id,
        requested_at=now_ts,
        reviewed_at=None,
        review_notes=NO_APPROVAL_NOTE[:300],
    )
    db.add(req)
    invoice.refund_requests.append(req)  # so the next line of a whole-invoice cancellation sees this refund

    line.status = "CANCELLED"
    if line.test_order:
        line.test_order.status = "CANCELLED"
        db.add(TestOrderEvent(
            tenant_id=tenant_id,
            test_order_id=line.test_order.id,
            event_type="CANCELLED_PRE_LOCK",
            stage="CANCELLED",
            description="Test cancelled before the sample was taken.",
            notes=reason,
            actor_id=actor_id,
            actor_role=acting_role,
            created_at=now_ts,
        ))
    invoice.refund_due = max(0, invoice.refund_due + req.amount)
    _apply_line_cancellation(invoice, outcome)
    recompute_invoice_refund_status(invoice)
    db.flush()
    accounting_service.post_line_cancelled(db, invoice, line, net_before, req.amount, actor_id)  # Prompt 18
    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="PRE_LOCK_CANCELLATION",
        entity_type="REFUND_REQUEST",
        entity_id=req.id,
        acting_role=acting_role,
        actor_id=actor_id,
        after_value=f"{scope}: Invoice {invoice.id} Line {line.id} cancelled, refund Tk {req.amount}, retained Tk {outcome['retained_amount']}, due Tk {outcome['due_after']}. Reason: {reason}",
    )
    return req


def initiate_refund_request(
    db: Session,
    tenant_id: str,
    data: RefundRequestCreate,
    requested_by_id: int,
    acting_role: str = "RECEPTIONIST",
) -> RefundRequest:
    """Prompt 13A: pre-lock cancellation of ONE unlocked line, executed immediately (the Prompt 13
    Admin/Owner approval step is removed for this path only; D15 and imaging-started keep theirs).
    The amount is always computed by the server (a client amount / request_type is ignored). A locked
    line is refused with a distinct 409 (SAMPLE_ALREADY_TAKEN). Prompt 13B: this never pays anything out;
    a refund due is left APPROVED for the separate disburse step."""
    line_id = data.invoice_line_id
    if not line_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose the test line to cancel.")

    # Row lock: serialises a cancellation against a concurrent Sample Taken / second cancellation.
    line = db.execute(
        select(InvoiceLine).where(InvoiceLine.id == line_id, InvoiceLine.tenant_id == tenant_id).with_for_update()
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice line not found.")
    if data.invoice_id and data.invoice_id != line.invoice_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This line does not belong to that invoice.")
    if line.invoice.status != "CONFIRMED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a Confirmed invoice line can be cancelled.")

    blocker = line_cancellation_blocker(db, line)
    if blocker:
        raise _blocker_error(blocker)

    reason = (data.reason or "").strip() or "(no reason given)"
    req = _cancel_line_now(db, tenant_id, line, requested_by_id, acting_role, reason, "Line")
    return req


# --- Prompt 13A: whole-invoice pre-lock cancellation -------------------------------------------------
class _SimRequest:
    def __init__(self, amount: int):
        self.id = -1
        self.status = "APPROVED"
        self.amount = amount


class _SimInvoice:
    """Read-only stand-in so the whole-invoice preview can reuse compute_cancellation_outcome line by
    line without touching the real invoice."""
    def __init__(self, invoice: Invoice):
        self.net = invoice.net
        self.paid = invoice.paid
        self.urgent_fee = getattr(invoice, "urgent_fee", 0) or 0
        self.refund_requests = list(invoice.refund_requests)


def invoice_cancellable_lines(db: Session, invoice: Invoice, lock: bool = False) -> List[InvoiceLine]:
    """Active lines of the invoice, or an HTTP 409/400 explaining why the whole invoice cannot be cancelled."""
    if invoice.status != "CONFIRMED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a Confirmed invoice can be cancelled.")
    if lock:
        db.execute(select(InvoiceLine.id).where(InvoiceLine.invoice_id == invoice.id).order_by(InvoiceLine.id).with_for_update()).all()
    lines = sorted((l for l in invoice.lines if l.status != "CANCELLED"), key=lambda l: l.id)
    if not lines:
        raise _blocker_error("ALREADY_CANCELLED")
    # Whole bill: only if NO line is locked. Never cancel just the unlocked subset.
    for l in lines:
        if line_lock_blocker(db, l):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
                "code": "SAMPLE_ALREADY_TAKEN",
                "message": "At least one test on this invoice already has its sample taken, so the whole invoice cannot be cancelled. "
                           "Cancel the untouched tests one by one instead, or ask Admin/Owner about the Not Performed (D15) path for the rest.",
            })
    for l in lines:
        if line_cancellation_blocker(db, l) == "REQUEST_PENDING":
            raise _blocker_error("REQUEST_PENDING")
    return lines


def simulate_invoice_cancellation(invoice: Invoice, lines: List[InvoiceLine]) -> Dict[str, object]:
    """Whole-invoice breakdown: compute_cancellation_outcome per line in order, each seeing the refunds of
    the lines before it. Totals: refund is the sum; retained / due / new total are the final step's."""
    sim = _SimInvoice(invoice)
    rows, total_refund, last = [], 0, None
    for l in lines:
        out = compute_cancellation_outcome(sim, l)
        rows.append({"invoice_line_id": l.id, "test_name": l.test_name_snapshot, "line_price": out["line_price"], "refund_amount": out["refund_amount"]})
        total_refund += out["refund_amount"]
        sim.net = out["net_after"]
        sim.refund_requests.append(_SimRequest(out["refund_amount"]))
        last = out
    return {
        "invoice_total": max(0, invoice.net), "paid_total": max(0, invoice.paid),
        "lines": rows, "total_refund": total_refund,
        "retained_amount": last["retained_amount"], "due_after": last["due_after"], "net_after": last["net_after"],
    }


def cancel_invoice_now(
    db: Session,
    tenant_id: str,
    invoice_id: int,
    reason: Optional[str],
    actor_id: int,
    acting_role: str,
) -> List[RefundRequest]:
    """Prompt 13A: cancels EVERY line of a Confirmed invoice together, only if no line is locked
    (otherwise 409 and nothing changes). One transaction: all lines, invoice figures, audit rows."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    lines = invoice_cancellable_lines(db, invoice, lock=True)
    reason_txt = (reason or "").strip() or "(no reason given)"
    reqs = [_cancel_line_now(db, tenant_id, l, actor_id, acting_role, reason_txt, "Whole invoice") for l in lines]
    log_audit_event(
        db=db, tenant_id=tenant_id, action="PRE_LOCK_INVOICE_CANCELLATION", entity_type="INVOICE", entity_id=invoice.id,
        acting_role=acting_role, actor_id=actor_id,
        after_value=f"All {len(lines)} lines cancelled together before any sample was taken; total refund Tk {sum(r.amount for r in reqs)}. Reason: {reason_txt}",
    )
    return reqs


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
        line = req.invoice_line
        if req.request_type == "PRE_SAMPLE_CANCELLATION":
            # Prompt 13: a reason is mandatory when approving a pre-lock cancellation.
            if not (review_notes or "").strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to approve a cancellation.")
            # The sample may have been taken after the request was filed: it is no longer a pre-lock case.
            if line_lock_blocker(db, line) == "SAMPLE_ALREADY_TAKEN":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "SAMPLE_ALREADY_TAKEN", "message": "The sample was taken after this request was filed. Reject this request; cancellation now follows the D15 'Not Performed' path."},
                )
        req.status = "APPROVED"
        invoice = req.invoice

        # Prompt 10E Part 1: the amount is recomputed from the invoice state at approval time
        # (never the requested/client amount): refund = max(0, retained_paid - net_after).
        outcome = compute_cancellation_outcome(invoice, line, exclude_request_id=req.id)
        req.amount = outcome["refund_amount"]

        # Execute financial line cancellation
        line.status = "CANCELLED"
        if line.test_order:
            line.test_order.status = "CANCELLED"
            if req.request_type == "D15_NOT_PERFORMED":
                line.test_order.outcome = "NOT_PERFORMED"

        net_before = invoice.net
        invoice.refund_due = max(0, invoice.refund_due + req.amount)
        if req.amount == 0:
            # Nothing to give back (the remaining tests still cost at least what was paid):
            # the line is cancelled and the request is closed; there is nothing to disburse.
            req.status = ZERO_REFUND_CLOSED_STATUS
        _apply_line_cancellation(invoice, outcome)

        # Section 5 Fix 4: REFUND_APPROVED (awaiting disbursement), never FULLY_REFUNDED here.
        recompute_invoice_refund_status(invoice)
        accounting_service.post_line_cancelled(db, invoice, line, net_before, req.amount, reviewer_id)  # Prompt 18

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
        recompute_invoice_refund_status(invoice)

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

    accounting_service.require_open_day(db, tenant_id)  # Prompt 18B: paying a refund out needs an OPEN day
    now_ts = utc_now()
    invoice = req.invoice
    method_norm = normalize_channel(data.method)  # Prompt 10E: CARD -> POS_CARD alias; ROCKET / OTHER supported

    # Fix 1: Validate disbursement method against invoice recorded payments (D18, M29)
    paid_channels: Dict[str, int] = {}
    for p in invoice.payments:
        pm = normalize_channel(p.method)
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
    accounting_service.post_refund_disbursed(db, tenant_id, req, method_norm, disburser_id)  # Prompt 18

    # Recompute invoice refund_status
    recompute_invoice_refund_status(invoice)

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

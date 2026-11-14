from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy import select, or_, and_, desc, func
from sqlalchemy.orm import Session
from backend.app.models.patient import Patient
from backend.app.models.visit import Visit
from backend.app.models.referrer import Referrer
from backend.app.models.test import Test, TestDestination
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.payment import Payment
from backend.app.models.user import Staff
from backend.app.models.tenant import Tenant
from backend.app.models.test_order import TestOrder, AssignmentHistory, TestOrderEvent
from backend.app.models.business_day import BusinessDay, BusinessDayChannelBalance
from backend.app.core.timezone import utc_now
from backend.app.schemas.invoice import InvoiceConfirmRequest, InvoiceLineCreate
from backend.app.services.sequence_service import (
    generate_invoice_number,
    generate_visit_number,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.core.payment_channels import validate_channel
from backend.app.services.business_day_service import add_to_channel_balance
from backend.app.services import accounting_service
from backend.app.services.routing_service import route_new_order


DRAFT_STATUS = "DRAFT"
CONFIRMED_STATUS = "CONFIRMED"

# ---------------------------------------------------------------------------
# Prompt 10E Part 5: urgent fee (backend is the single source of truth).
# Replicates the New Invoice UI rule exactly: for every urgent line,
#     fee = Math.max(100, Math.round(price * 0.2))
# i.e. 20% of the line's list price, rounded half up to whole taka, with a MINIMUM of 100.
# (The UI note "max 100, 20%" refers to JavaScript's Math.max, which acts as a floor.)
# The fee is added on top of gross; discounts never apply to it; it is included in net/due.
# ---------------------------------------------------------------------------
URGENT_FEE_PERCENT = 20
URGENT_FEE_MINIMUM = 100


def compute_urgent_fee(unit_price: int) -> int:
    """Urgent fee for one line from its list price (whole taka)."""
    price = max(0, int(unit_price))
    # round(price * 20 / 100) half-up, in integers (price * 0.2 never ends in .5 for whole taka)
    pct_fee = (price * URGENT_FEE_PERCENT * 2 + 100) // 200
    return max(URGENT_FEE_MINIMUM, pct_fee)


def _verify_patient(db: Session, tenant_id: str, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )
    return patient


def _load_tests(db: Session, tenant_id: str, data: InvoiceConfirmRequest) -> dict:
    test_ids = [line.test_id for line in data.lines]
    stmt_tests = select(Test).where(Test.tenant_id == tenant_id, Test.id.in_(test_ids))
    tests_by_id = {t.id: t for t in db.execute(stmt_tests).scalars().all()}
    if len(tests_by_id) != len(set(test_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected tests do not exist or belong to another center.",
        )
    # Prompt 11: a soft-deleted catalog test cannot be billed again (old invoice lines keep their snapshot)
    deleted = [t for t in tests_by_id.values() if t.deleted_at is not None]
    if deleted:
        names = ", ".join(f"{t.code} {t.name}" for t in deleted)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deleted test(s) cannot be billed: {names}. Remove them from the bill.",
        )
    return tests_by_id


def _verify_referrer_choice(db: Session, tenant_id: str, referrer_id: Optional[int], label: str, unchanged_id: Optional[int] = None) -> None:
    """Prompt 11: a doctor / referrer chosen for a NEW bill must exist and not be soft-deleted.
    A draft that already carries the id (unchanged_id) may keep saving; Finalize re-checks."""
    if referrer_id is None or referrer_id == unchanged_id:
        return
    ref = db.get(Referrer, referrer_id)
    if not ref or ref.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label} not found.")
    if ref.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} '{ref.name}' was deleted and cannot be chosen for a new bill.",
        )


def _pct_half_up(amount: int, pct: int) -> int:
    """amount * pct / 100 rounded half up (JavaScript Math.round), whole taka."""
    return (int(amount) * int(pct) * 2 + 100) // 200


def compute_invoice_totals(data: InvoiceConfirmRequest, tests_by_id: dict) -> dict:
    """Pure calculation of line nets, gross, discount and net payable (no DB writes).
    Used by both Save Draft and Finalize so a draft shows the same totals it will finalize with."""
    gross_total = 0
    calculated_lines = []
    line_discount_sum = 0
    urgent_fee_total = 0
    bill_discount_active = data.bill_discount_type in ("PERCENTAGE", "AMOUNT") and data.bill_discount_value > 0
    for line_req in data.lines:
        test_obj = tests_by_id[line_req.test_id]
        unit_price = test_obj.price
        gross_total += unit_price
        line_discount_amt = 0
        if line_req.discount_type == "PERCENTAGE":
            pct = min(max(0, line_req.discount_value), 100)
            line_discount_amt = _pct_half_up(unit_price, pct)  # same rounding as the UI (Math.round)
        elif line_req.discount_type == "AMOUNT":
            line_discount_amt = max(0, line_req.discount_value)
        # Cap line discount at unit price (cannot become negative net)
        line_discount_amt = min(line_discount_amt, unit_price)
        if bill_discount_active:
            # Master Discount active: individual discounts are inactive in calculations
            # (their type/value stay preserved on the line), matching the UI preview.
            line_discount_amt = 0
        line_discount_sum += line_discount_amt
        is_urgent = bool(line_req.urgent or data.urgent)
        line_fee = compute_urgent_fee(unit_price) if is_urgent else 0
        urgent_fee_total += line_fee
        calculated_lines.append({
            "test_obj": test_obj,
            "unit_price": unit_price,
            "discount_type": line_req.discount_type,
            "discount_value": line_req.discount_value,
            "discount_amount": line_discount_amt,
            "net_price": unit_price - line_discount_amt,
            "urgent": is_urgent,
            "urgent_fee": line_fee,
        })
    # Bill-level discount overrides line discounts when requested
    final_discount_total = line_discount_sum
    if data.bill_discount_type in ("PERCENTAGE", "AMOUNT") and data.bill_discount_value > 0:
        if data.bill_discount_type == "PERCENTAGE":
            pct = min(max(0, data.bill_discount_value), 100)
            final_discount_total = _pct_half_up(gross_total, pct)
        else:
            final_discount_total = min(data.bill_discount_value, gross_total)
    return {
        "lines": calculated_lines,
        "gross": gross_total,
        "discount": final_discount_total,
        "urgent_fee": urgent_fee_total,
        "net": max(0, gross_total - final_discount_total) + urgent_fee_total,
    }


def validate_finalize_demographics(data: InvoiceConfirmRequest) -> None:
    """Prompt 10E Part 3: Finalize requires both age and gender (a draft may be incomplete)."""
    missing = []
    if data.age_value is None:
        missing.append("age")
    if not data.gender:
        missing.append("gender")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient {' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} required to finalize the invoice.",
        )


def _age_in_days(age_value: int, age_unit: str) -> float:
    unit = (age_unit or "years").lower()
    if unit == "days":
        return float(age_value)
    if unit == "months":
        return float(age_value * 30)
    return float(age_value * 365)


NO_DISCOUNT_TEXT = "No discount"


def discount_state_text(data: InvoiceConfirmRequest, tests_by_id: Optional[dict] = None, total: Optional[int] = None) -> str:
    """Prompt 19B: audit text for the discount setup of a bill: master discount mode/value, and each line's own
    discount mode/value (kept even while the master is active, because the line values stay preserved).
    Returns NO_DISCOUNT_TEXT when nothing is set."""
    parts = []
    master = data.bill_discount_type in ("PERCENTAGE", "AMOUNT") and data.bill_discount_value > 0
    if master:
        parts.append(f"Master {data.bill_discount_type} {data.bill_discount_value}")
    line_bits = []
    for ln in data.lines:
        if ln.discount_type in ("PERCENTAGE", "AMOUNT") and ln.discount_value > 0:
            t = (tests_by_id or {}).get(ln.test_id)
            name = getattr(t, "name", None) or f"test #{ln.test_id}"
            line_bits.append(f"{name}: {ln.discount_type} {ln.discount_value}")
    if line_bits:
        parts.append("Line " + "; ".join(line_bits) + (" (inactive while the master discount is active)" if master else ""))
    if not parts:
        return NO_DISCOUNT_TEXT
    if total is not None:
        parts.append(f"Total discount Tk {total}")
    return " | ".join(parts)


def _strip_total(text: str) -> str:
    return text.split(" | Total discount", 1)[0]


def _payload_discount_text(db: Session, tenant_id: str, payload: Optional[dict]) -> str:
    """Discount text of a previously saved draft payload (the 'before' side); a payload that can no longer be
    parsed is reported as such instead of guessed."""
    if not payload:
        return NO_DISCOUNT_TEXT
    try:
        old = InvoiceConfirmRequest.model_validate(payload)
    except Exception:
        return "Previous draft discount could not be read"
    try:
        return discount_state_text(old, _load_tests(db, tenant_id, old))
    except HTTPException:
        return discount_state_text(old)


def _log_discount_event(db: Session, tenant_id: str, action: str, invoice: Invoice, before: str, after: str,
                        actor_id: int, acting_role: str) -> None:
    log_audit_event(db=db, tenant_id=tenant_id, action=action, entity_type="INVOICE", entity_id=invoice.id,
                    acting_role=acting_role, actor_id=actor_id, before_value=before, after_value=after)


def save_invoice_draft(
    db: Session,
    tenant_id: str,
    data: InvoiceConfirmRequest,
    creator_id: int,
    acting_role: str = "RECEPTIONIST",
    draft_id: Optional[int] = None,
) -> Invoice:
    """Prompt 10D Part 3: creates or updates a DRAFT invoice.

    A draft has NO operational effect: no visit, no invoice number from the sequence,
    no invoice lines, no test orders / worklist entries, no samples, no payment, no
    business-day totals, no commission and no ledger. The form is stored in draft_payload.
    Totals are stored for display only; due is 0 so drafts never appear in dues lists.
    """
    _verify_patient(db, tenant_id, data.patient_id)
    tests_by_id = _load_tests(db, tenant_id, data)
    existing = db.get(Invoice, draft_id) if draft_id is not None else None
    _verify_referrer_choice(db, tenant_id, data.prescribed_by_id, "Doctor",
                            existing.prescribed_by_id if existing else None)
    _verify_referrer_choice(db, tenant_id, data.referrer_id, "Referrer",
                            existing.referrer_id if existing else None)
    totals = compute_invoice_totals(data, tests_by_id)
    if data.initial_payment_amount > totals["net"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Overpayment is forbidden. Amount entered (Tk {data.initial_payment_amount}) exceeds net payable (Tk {totals['net']}).",
        )
    payload = data.model_dump(mode="json")

    if draft_id is not None:
        invoice = db.execute(
            select(Invoice).where(Invoice.id == draft_id, Invoice.tenant_id == tenant_id).with_for_update()
        ).scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
        if invoice.status != DRAFT_STATUS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only DRAFT invoices can be edited. This invoice is already finalized.",
            )
        action = "UPDATE_INVOICE_DRAFT"
        discount_before = _payload_discount_text(db, tenant_id, invoice.draft_payload)
    else:
        placeholder = f"DRAFT-{uuid4().hex[:10].upper()}"
        invoice = Invoice(
            tenant_id=tenant_id,
            visit_id=None,
            invoice_no=placeholder,
            temp_invoice_id=placeholder,
            status=DRAFT_STATUS,
            created_by_id=creator_id,
        )
        db.add(invoice)
        action = "SAVE_INVOICE_DRAFT"
        discount_before = NO_DISCOUNT_TEXT

    invoice.patient_id = data.patient_id
    invoice.prescribed_by_id = data.prescribed_by_id
    invoice.referrer_id = data.referrer_id
    invoice.payment_status = "UNPAID"
    invoice.refund_status = "NO_REFUND"
    invoice.gross = totals["gross"]
    invoice.discount = totals["discount"]
    invoice.net = totals["net"]
    invoice.paid = 0
    invoice.due = 0
    invoice.refund_due = 0
    invoice.urgent = data.urgent
    invoice.urgent_fee = totals["urgent_fee"]
    invoice.draft_payload = payload
    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=action,
        entity_type="INVOICE",
        entity_id=invoice.id,
        acting_role=acting_role,
        actor_id=creator_id,
        after_value=f"Draft {invoice.invoice_no}: {len(data.lines)} test(s), Net (preview): {invoice.net}",
    )
    # Prompt 19B: a dedicated discount event with real before/after, only when the discount setup changed
    discount_after = discount_state_text(data, tests_by_id, totals["discount"])
    if _strip_total(discount_before) != _strip_total(discount_after):
        _log_discount_event(db, tenant_id, "INVOICE_DISCOUNT_CHANGED", invoice, discount_before, discount_after,
                            creator_id, acting_role)
    return invoice


def finalize_invoice_draft(
    db: Session,
    tenant_id: str,
    invoice_id: int,
    creator_id: int,
    acting_role: str = "RECEPTIONIST",
    data: Optional[InvoiceConfirmRequest] = None,
) -> Invoice:
    """Prompt 10D Part 3: Finalize a DRAFT. Assigns the real invoice number and performs every
    confirmation side effect (visit, lines, test orders and routing, payment, drawer balance,
    CONFIRM_INVOICE audit). Not repeatable: a non-DRAFT invoice returns 409."""
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id).with_for_update()
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if invoice.status != DRAFT_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invoice is already finalized. Finalize cannot be repeated.",
        )
    discount_before = _payload_discount_text(db, tenant_id, invoice.draft_payload)  # Prompt 19B: before overwriting
    if data is None:
        if not invoice.draft_payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft has no saved content.")
        data = InvoiceConfirmRequest.model_validate(invoice.draft_payload)
    else:
        invoice.draft_payload = data.model_dump(mode="json")
    return _confirm_invoice(db, tenant_id, data, creator_id, acting_role, draft_invoice=invoice,
                            discount_before=discount_before)


def create_and_confirm_invoice(
    db: Session,
    tenant_id: str,
    data: InvoiceConfirmRequest,
    creator_id: int,
    acting_role: str = "RECEPTIONIST",
) -> Invoice:
    """Creates and finalizes a new invoice in one step (Finalize pressed on an unsaved form)."""
    return _confirm_invoice(db, tenant_id, data, creator_id, acting_role, draft_invoice=None)


def _confirm_invoice(
    db: Session,
    tenant_id: str,
    data: InvoiceConfirmRequest,
    creator_id: int,
    acting_role: str = "RECEPTIONIST",
    draft_invoice: Optional[Invoice] = None,
    discount_before: str = NO_DISCOUNT_TEXT,
) -> Invoice:
    """
    Creates Visit, Invoice, Snapshot InvoiceLines, TestOrders, and Initial Payment
    enforcing all discount caps and billing invariants inside a single transaction.
    When draft_invoice is given, that DRAFT row is finalized in place.
    """
    # 1. Verify Patient and the visit demographics (Prompt 10E Part 3)
    patient = _verify_patient(db, tenant_id, data.patient_id)
    validate_finalize_demographics(data)
    if patient.gender != data.gender:
        # The form may update the stored patient value; earlier visits keep their snapshot.
        patient.gender = data.gender

    # 2. Prompt 18B: confirming a bill needs an OPEN day (409 closed / reopened, 400 none ever opened)
    active_day = accounting_service.require_open_day(db, tenant_id)

    # 3. Create Visit
    visit_number = generate_visit_number(db, tenant_id)
    visit = Visit(
        tenant_id=tenant_id,
        patient_id=patient.id,
        visit_number=visit_number,
        age_value=data.age_value,
        age_unit=data.age_unit,
        age_days=_age_in_days(data.age_value, data.age_unit),
        gender=data.gender,
        created_by_id=creator_id,
    )
    db.add(visit)
    db.flush()

    # 4-6. Fetch tests, calculate line items, line discounts, bill discount and net
    tests_by_id = _load_tests(db, tenant_id, data)
    _verify_referrer_choice(db, tenant_id, data.prescribed_by_id, "Doctor")
    _verify_referrer_choice(db, tenant_id, data.referrer_id, "Referrer")
    totals = compute_invoice_totals(data, tests_by_id)
    calculated_lines = totals["lines"]
    gross_total = totals["gross"]
    final_discount_total = totals["discount"]
    final_net_payable = totals["net"]

    # 7. Validate Initial Payment
    initial_payment = data.initial_payment_amount
    if initial_payment > final_net_payable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Overpayment is forbidden. Amount entered (Tk {initial_payment}) exceeds net payable (Tk {final_net_payable}).",
        )

    # Prompt 10E Part 4: channel must be one of the backend channels; OTHER needs a name
    pay_channel, pay_channel_detail = validate_channel(data.initial_payment_method, data.initial_payment_channel_detail)
    data.initial_payment_method = pay_channel

    # Validate non-cash digital references
    if initial_payment > 0 and data.initial_payment_method != "CASH":
        if not data.initial_payment_reference or len(data.initial_payment_reference.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction reference is required for digital payment method ({data.initial_payment_method}).",
            )
        # Check duplicate reference
        clean_ref = data.initial_payment_reference.strip()
        dup_ref = db.execute(
            select(Payment).where(
                Payment.tenant_id == tenant_id,
                Payment.reference == clean_ref,
            )
        ).scalar_one_or_none()
        if dup_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment reference '{clean_ref}' has already been recorded.",
            )

    due_amount = final_net_payable - initial_payment
    payment_status = "PAID" if due_amount == 0 else ("PARTLY_PAID" if initial_payment > 0 else "UNPAID")

    # 8. Create (or finalize) Invoice Header. The real invoice number is assigned only here,
    # at Finalize, so drafts never consume invoice numbers.
    invoice_no = generate_invoice_number(db, tenant_id)
    header_fields = dict(
        tenant_id=tenant_id,
        visit_id=visit.id,
        patient_id=patient.id,
        invoice_no=invoice_no,
        prescribed_by_id=data.prescribed_by_id,
        referrer_id=data.referrer_id,
        status=CONFIRMED_STATUS,
        payment_status=payment_status,
        gross=gross_total,
        discount=final_discount_total,
        net=final_net_payable,
        paid=initial_payment,
        due=due_amount,
        refund_due=0,
        urgent=data.urgent,
        urgent_fee=totals["urgent_fee"],
        finalized_at=utc_now(),
    )
    if draft_invoice is not None:
        invoice = draft_invoice
        for k, v in header_fields.items():
            setattr(invoice, k, v)
    else:
        invoice = Invoice(created_by_id=creator_id, **header_fields)
        db.add(invoice)
    db.flush()

    # 9. Create Invoice Lines and Test Orders with Automatic Assignment & Task Routing (Module 10)
    for line_info in calculated_lines:
        t_obj = line_info["test_obj"]
        inv_line = InvoiceLine(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            test_id=t_obj.id,
            test_code_snapshot=t_obj.code,
            test_name_snapshot=t_obj.name,
            department_snapshot=t_obj.department,
            unit_price_snapshot=line_info["unit_price"],
            discount_type=line_info["discount_type"],
            discount_value=line_info["discount_value"],
            discount_amount=line_info["discount_amount"],
            net_price=line_info["net_price"],
            urgent=line_info["urgent"],
            urgent_fee=line_info["urgent_fee"],
            status="CONFIRMED",
        )
        db.add(inv_line)
        db.flush()

        # Idempotency check: Ensure order creation is idempotent
        existing_order = db.execute(
            select(TestOrder).where(
                TestOrder.tenant_id == tenant_id,
                TestOrder.invoice_line_id == inv_line.id,
            )
        ).scalar_one_or_none()
        if existing_order:
            continue

        # Prompt 10E Part 7: room-based routing (a room, never one technician)
        now_ts = utc_now()
        assigned_status, order_section, dest_name, assignment_reason = route_new_order(db, tenant_id, t_obj)
        assigned_staff_id = None

        test_order = TestOrder(
            tenant_id=tenant_id,
            invoice_line_id=inv_line.id,
            status=assigned_status,
            urgent=inv_line.urgent,
            department=t_obj.department,
            performing_role=getattr(t_obj, "performing_role", "LAB_TECH"),
            turnaround_hours=getattr(t_obj, "turnaround_hours", None),
            sample_route="QUICK",
            lab_section=order_section,
            assigned_to_id=assigned_staff_id,
            assigned_destination=dest_name,
            assigned_at=now_ts if (assigned_staff_id or dest_name) else None,
            assigned_by_id=creator_id if (assigned_staff_id or dest_name) else None,
            created_at=now_ts,
        )
        db.add(test_order)
        db.flush()

        # Record initial routing in AssignmentHistory
        if dest_name or assigned_staff_id:
            history = AssignmentHistory(
                tenant_id=tenant_id,
                test_order_id=test_order.id,
                previous_assignee="SYSTEM",
                new_assignee=dest_name or f"Staff #{assigned_staff_id}",
                reason=assignment_reason or "Initial invoice confirmation routing",
                changed_by_id=creator_id,
                changed_at=now_ts,
            )
            db.add(history)

        # Record initial event in TestOrderEvent lifecycle timeline
        initial_event = TestOrderEvent(
            tenant_id=tenant_id,
            test_order_id=test_order.id,
            event_type="ORDER_CREATED",
            stage=assigned_status,
            description=f"Task created from Invoice #{invoice.invoice_no}. Assigned to: {dest_name or 'Unassigned Queue'}",
            notes=assignment_reason,
            actor_id=creator_id,
            actor_name="Intake Receptionist",
            actor_role="RECEPTIONIST",
            created_at=now_ts,
        )
        db.add(initial_event)

    # 10. Record Initial Payment (if provided)
    pmt = None
    if initial_payment > 0:
        change_due = 0
        if data.initial_payment_method == "CASH" and data.cash_tendered:
            if data.cash_tendered > initial_payment:
                change_due = data.cash_tendered - initial_payment

        pmt = Payment(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            business_day_id=active_day.id if active_day else None,
            amount=initial_payment,
            method=data.initial_payment_method,
            reference=data.initial_payment_reference.strip() if data.initial_payment_reference else None,
            channel_detail=pay_channel_detail,
            change_amount=change_due,
            received_by_id=creator_id,
        )
        db.add(pmt)

        # Update business day channel balance if open (missing channel rows are created safely)
        if active_day:
            add_to_channel_balance(db, tenant_id, active_day, data.initial_payment_method, initial_payment)

    db.flush()

    # Prompt 19B: dedicated discount and initial-payment events (separate from CONFIRM_INVOICE below)
    discount_after = discount_state_text(data, tests_by_id, final_discount_total)
    if discount_after != NO_DISCOUNT_TEXT or _strip_total(discount_before) != _strip_total(discount_after):
        _log_discount_event(db, tenant_id, "INVOICE_DISCOUNT_CONFIRMED", invoice, discount_before, discount_after,
                            creator_id, acting_role)
    if pmt is not None:
        payer = f"{patient.name} ({patient.patient_code})"
        receiver = db.get(Staff, creator_id)
        log_audit_event(
            db=db, tenant_id=tenant_id, action="INVOICE_INITIAL_PAYMENT", entity_type="PAYMENT", entity_id=pmt.id,
            acting_role=acting_role, actor_id=creator_id,
            before_value=f"Invoice {invoice.invoice_no}: paid Tk 0, net Tk {final_net_payable}",
            after_value=(f"Tk {pmt.amount} via {pmt.method}" + (f" ({pmt.channel_detail})" if pmt.channel_detail else "")
                         + (f", ref {pmt.reference}" if pmt.reference else "")
                         + f" | payer: {payer} | received by: {receiver.display_name if receiver else creator_id}"
                         + f" | invoice {invoice.invoice_no}: paid Tk {invoice.paid}, due Tk {invoice.due}"),
        )

    # Prompt 18: journal (bill confirmed, then the initial payment); no change to the billing logic above
    accounting_service.post_bill_confirmed(db, invoice, creator_id, active_day.id if active_day else None)
    if pmt is not None:
        accounting_service.post_payment_received(db, tenant_id, invoice, pmt, creator_id)

    # 11. Audit Log
    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="CONFIRM_INVOICE",
        entity_type="INVOICE",
        entity_id=invoice.id,
        acting_role=acting_role,
        actor_id=creator_id,
        after_value=(
            f"Invoice: {invoice.invoice_no}, Gross: {invoice.gross}, Net: {invoice.net}, Paid: {invoice.paid}, Due: {invoice.due}"
            + (f" (finalized from draft {invoice.temp_invoice_id})" if draft_invoice is not None else "")
        ),
    )
    return invoice


def search_invoices(
    db: Session,
    tenant_id: str,
    query: Optional[str] = None,
    payment_status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
) -> List[Invoice]:
    """Search and filter invoices by query (no, phone, patient name), status, date range."""
    stmt = (
        select(Invoice)
        .join(Invoice.patient)
        .where(Invoice.tenant_id == tenant_id)
        .order_by(desc(Invoice.created_at))
    )

    if query and query.strip():
        q = query.strip()
        stmt = stmt.where(
            or_(
                Invoice.invoice_no.ilike(f"%{q}%"),
                Patient.name.ilike(f"%{q}%"),
                Patient.phone.ilike(f"%{q}%"),
                Patient.patient_code.ilike(f"%{q}%"),
            )
        )

    if payment_status and payment_status.strip():
        norm = payment_status.strip().upper()
        if norm not in ("ALL", "ALL PAYMENTS", "DRAFT"):
            # Payment / refund filters describe finalized money; drafts carry no payment state.
            stmt = stmt.where(Invoice.status != DRAFT_STATUS)
        if norm in ("ALL", "ALL PAYMENTS"):
            pass
        elif norm == "DRAFT":
            stmt = stmt.where(Invoice.status == DRAFT_STATUS)
        elif norm in ("PAID",):
            # Paid: payment_status is PAID and not fully refunded
            stmt = stmt.where(
                Invoice.payment_status == "PAID",
                or_(Invoice.refund_status.is_(None), Invoice.refund_status != "FULLY_REFUNDED"),
            )
        elif norm in ("UNPAID", "DUE"):
            # Unpaid: payment_status is UNPAID (or paid == 0 and due > 0)
            stmt = stmt.where(
                or_(Invoice.payment_status == "UNPAID", and_(Invoice.paid == 0, Invoice.due > 0))
            )
        elif norm in ("PARTIAL DUE", "PARTIAL_DUE", "PARTIAL", "PARTLY_PAID"):
            # Partial Due: payment_status is PARTLY_PAID (or paid > 0 and due > 0)
            stmt = stmt.where(
                or_(Invoice.payment_status == "PARTLY_PAID", and_(Invoice.paid > 0, Invoice.due > 0))
            )
        elif norm in ("PARTIALLY REFUNDED", "PARTIALLY_REFUNDED"):
            # Partially Refunded: refund_status is PARTIALLY_REFUNDED
            stmt = stmt.where(Invoice.refund_status == "PARTIALLY_REFUNDED")
        elif norm in ("FULLY REFUNDED", "FULLY_REFUNDED", "REFUNDED"):
            # Fully Refunded: refund_status is FULLY_REFUNDED (or payment_status is REFUNDED)
            stmt = stmt.where(
                or_(Invoice.refund_status == "FULLY_REFUNDED", Invoice.payment_status == "REFUNDED")
            )
        else:
            # Fallback direct match
            stmt = stmt.where(Invoice.payment_status == norm)

    if date_from:
        stmt = stmt.where(Invoice.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.created_at <= date_to)

    return list(db.execute(stmt.limit(limit)).scalars().all())



def discard_invoice_draft(db: Session, actor, invoice_id: int) -> Invoice:
    """Prompt 11 (Category B): permanently delete a DRAFT invoice. No reason, no restore.

    Allowed for the staff member who created the draft, or ADMIN/OWNER. Only DRAFT status; a draft
    has no operational effect by design (no visit, lines, test orders, samples, payments, refunds),
    and if any such row is found the discard is refused instead of deleting data something else
    depends on. The audit row is written first, in the same transaction, and survives the delete.
    """
    from backend.app.models.payment import Payment
    from backend.app.models.refund import RefundRequest

    inv = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == actor.tenant_id).with_for_update()
    ).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if inv.status != DRAFT_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a DRAFT invoice can be discarded. Confirmed, finalized and cancelled invoices are permanent records.",
        )
    if actor.role not in ("ADMIN", "OWNER") and inv.created_by_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the staff member who created this draft, or an Admin/Owner, can discard it.",
        )
    has_children = (
        inv.visit_id is not None
        or db.execute(select(func.count(InvoiceLine.id)).where(InvoiceLine.invoice_id == inv.id)).scalar_one() > 0
        or db.execute(select(func.count(Payment.id)).where(Payment.invoice_id == inv.id)).scalar_one() > 0
        or db.execute(select(func.count(RefundRequest.id)).where(RefundRequest.invoice_id == inv.id)).scalar_one() > 0
    )
    if has_children:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This draft already has operational records (visit, lines, payments or refunds), so it was not discarded.",
        )
    temp_id = inv.temp_invoice_id or inv.invoice_no
    n_tests = len((inv.draft_payload or {}).get("lines", []) or [])
    log_audit_event(
        db=db,
        tenant_id=actor.tenant_id,
        action="INVOICE_DRAFT_DISCARDED",
        entity_type="INVOICE",
        entity_id=inv.id,
        acting_role=actor.role,
        actor_id=actor.id,
        before_value=f"Draft {temp_id} (patient {inv.patient_id}, {n_tests} test(s), created by staff {inv.created_by_id})",
        after_value="Discarded: draft permanently deleted (no reason required, no restore)",
    )
    db.delete(inv)
    db.flush()
    return inv

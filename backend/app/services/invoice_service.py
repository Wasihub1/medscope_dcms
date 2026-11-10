from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, or_, and_, desc
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


def create_and_confirm_invoice(
    db: Session,
    tenant_id: str,
    data: InvoiceConfirmRequest,
    creator_id: int,
    acting_role: str = "RECEPTIONIST",
) -> Invoice:
    """
    Creates Visit, Invoice, Snapshot InvoiceLines, TestOrders, and Initial Payment
    enforcing all discount caps and billing invariants inside a single transaction.
    """
    # 1. Verify Patient
    patient = db.get(Patient, data.patient_id)
    if not patient or patient.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found.",
        )

    # 2. Check active Business Day (if any is open, link it)
    active_day = (
        db.execute(
            select(BusinessDay).where(
                BusinessDay.tenant_id == tenant_id,
                BusinessDay.status == "OPEN",
            )
        )
        .scalars()
        .first()
    )

    # 3. Create Visit
    visit_number = generate_visit_number(db, tenant_id)
    visit = Visit(
        tenant_id=tenant_id,
        patient_id=patient.id,
        visit_number=visit_number,
        age_value=data.age_value,
        age_unit=data.age_unit,
        age_days=float(data.age_value * 365 if data.age_unit == "years" else data.age_value * 30),
        gender=data.gender,
        created_by_id=creator_id,
    )
    db.add(visit)
    db.flush()

    # 4. Fetch Tests and validate
    test_ids = [line.test_id for line in data.lines]
    stmt_tests = select(Test).where(Test.tenant_id == tenant_id, Test.id.in_(test_ids))
    tests_by_id = {t.id: t for t in db.execute(stmt_tests).scalars().all()}

    if len(tests_by_id) != len(set(test_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected tests do not exist or belong to another center.",
        )

    # 5. Calculate Line Items, Line Discounts & Gross
    gross_total = 0
    calculated_lines = []
    line_discount_sum = 0

    for line_req in data.lines:
        test_obj = tests_by_id[line_req.test_id]
        unit_price = test_obj.price
        gross_total += unit_price

        # Enforce Section 2.4 discount invariants
        line_discount_amt = 0
        if line_req.discount_type == "PERCENTAGE":
            pct = min(max(0, line_req.discount_value), 100)
            line_discount_amt = int(round((unit_price * pct) / 100.0))
        elif line_req.discount_type == "AMOUNT":
            line_discount_amt = max(0, line_req.discount_value)

        # Cap line discount at unit price (cannot become negative net)
        line_discount_amt = min(line_discount_amt, unit_price)
        line_net = unit_price - line_discount_amt
        line_discount_sum += line_discount_amt

        calculated_lines.append({
            "test_obj": test_obj,
            "unit_price": unit_price,
            "discount_type": line_req.discount_type,
            "discount_value": line_req.discount_value,
            "discount_amount": line_discount_amt,
            "net_price": line_net,
            "urgent": line_req.urgent or data.urgent,
        })

    # 6. Resolve Bill-Level Discount vs Line Discounts
    # If bill-level discount is requested, it overrides line discounts
    final_discount_total = line_discount_sum
    if data.bill_discount_type in ("PERCENTAGE", "AMOUNT") and data.bill_discount_value > 0:
        if data.bill_discount_type == "PERCENTAGE":
            pct = min(max(0, data.bill_discount_value), 100)
            final_discount_total = int(round((gross_total * pct) / 100.0))
        else:
            final_discount_total = min(data.bill_discount_value, gross_total)

    final_net_payable = max(0, gross_total - final_discount_total)

    # 7. Validate Initial Payment
    initial_payment = data.initial_payment_amount
    if initial_payment > final_net_payable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Overpayment is forbidden. Amount entered (Tk {initial_payment}) exceeds net payable (Tk {final_net_payable}).",
        )

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

    # 8. Create Invoice Header
    invoice_no = generate_invoice_number(db, tenant_id)
    invoice = Invoice(
        tenant_id=tenant_id,
        visit_id=visit.id,
        patient_id=patient.id,
        invoice_no=invoice_no,
        prescribed_by_id=data.prescribed_by_id,
        referrer_id=data.referrer_id,
        status="CONFIRMED",
        payment_status=payment_status,
        gross=gross_total,
        discount=final_discount_total,
        net=final_net_payable,
        paid=initial_payment,
        due=due_amount,
        refund_due=0,
        urgent=data.urgent,
        created_by_id=creator_id,
    )
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

        # Smart staff assignment and routing (Module 10 Section 4.2 & 4.3)
        now_ts = utc_now()
        assigned_staff_id = None
        dest_name = None
        assignment_reason = None

        if getattr(t_obj, "requires_doctor", False) or getattr(t_obj, "performing_role", "") == "DOCTOR":
            # Section 4.3: Visiting doctor workflow (e.g. Ultrasound)
            assigned_status = "AWAITING_DOCTOR"
            dest_name = t_obj.default_assignee or "Doctor Chamber"
            assignment_reason = "Routed to Visiting Doctor Queue (Awaiting Doctor)"
        elif getattr(t_obj, "is_outsourced", False):
            # Section 4.2: Outsourced lab test
            assigned_status = "PENDING"
            dest_name = "Outsourced Referral Lab"
            assignment_reason = "Marked for Outsourced Referral Processing"
        elif getattr(t_obj, "performing_role", "") == "LAB_TECH":
            # Section 4.2: Match eligible staff member by department and role
            eligible_staff = db.execute(
                select(Staff).where(
                    Staff.tenant_id == tenant_id,
                    Staff.active == True,
                    Staff.role == "LAB_TECH",
                    Staff.department == t_obj.department,
                )
            ).scalars().first()

            if eligible_staff:
                assigned_status = "ASSIGNED"
                assigned_staff_id = eligible_staff.id
                dest_name = eligible_staff.display_name
                assignment_reason = f"Automated routing by department ({t_obj.department}) to {eligible_staff.display_name}"
            else:
                # No eligible staff member available in this department:
                # Keep in appropriate unassigned/pending state, visible to management
                assigned_status = "UNASSIGNED"
                dest_name = t_obj.default_assignee or None
        else:
            auto_destination = t_obj.default_assignee or None
            assigned_status = "ASSIGNED" if auto_destination else "UNASSIGNED"
            dest_name = auto_destination

        test_order = TestOrder(
            tenant_id=tenant_id,
            invoice_line_id=inv_line.id,
            status=assigned_status,
            urgent=inv_line.urgent,
            department=t_obj.department,
            performing_role=getattr(t_obj, "performing_role", "LAB_TECH"),
            turnaround_hours=getattr(t_obj, "turnaround_hours", None),
            sample_route="QUICK",
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
            change_amount=change_due,
            received_by_id=creator_id,
        )
        db.add(pmt)

        # Update business day channel balance if open
        if active_day:
            channel_rec = db.execute(
                select(BusinessDayChannelBalance).where(
                    BusinessDayChannelBalance.business_day_id == active_day.id,
                    BusinessDayChannelBalance.channel == data.initial_payment_method,
                )
            ).scalar_one_or_none()
            if channel_rec:
                channel_rec.received_amount += initial_payment

    db.flush()

    # 11. Audit Log
    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="CONFIRM_INVOICE",
        entity_type="INVOICE",
        entity_id=invoice.id,
        acting_role=acting_role,
        actor_id=creator_id,
        after_value=f"Invoice: {invoice.invoice_no}, Gross: {invoice.gross}, Net: {invoice.net}, Paid: {invoice.paid}, Due: {invoice.due}",
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
        if norm in ("ALL", "ALL PAYMENTS"):
            pass
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


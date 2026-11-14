from datetime import datetime, timedelta
from backend.app.core.timezone import DHAKA_TZ
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.models.invoice import Invoice
from backend.app.models.patient import Patient
from backend.app.services.dues_service import age_bucket, bucket_clauses, due_age_days
from backend.app.models.payment import Payment
from backend.app.models.business_day import BusinessDay, BusinessDayChannelBalance
from backend.app.schemas.payment import DueInvoiceSummary, DueSettlementRequest
from backend.app.services.audit_service import log_audit_event
from backend.app.core.payment_channels import validate_channel
from backend.app.services.business_day_service import add_to_channel_balance
from backend.app.services import accounting_service


def list_due_invoices(
    db: Session,
    tenant_id: str,
    query: Optional[str] = None,
    limit: int = 50,
    bucket: Optional[str] = None,
    date_from=None,
    date_to=None,
) -> List[DueInvoiceSummary]:
    """Retrieves invoices that have an outstanding due balance (> 0)."""
    stmt = (
        select(Invoice)
        .join(Invoice.patient)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.due > 0,
            Invoice.status.not_in(["CANCELLED", "DRAFT"]),
        )
        .order_by(desc(Invoice.created_at))
    )

    if query and query.strip():
        q = query.strip()
        stmt = stmt.where(
            (Invoice.invoice_no.ilike(f"%{q}%"))
            | (Invoice.temp_invoice_id.ilike(f"%{q}%"))
            | (Patient.name.ilike(f"%{q}%"))
            | (Patient.phone.ilike(f"%{q}%"))
            | (Patient.patient_code.ilike(f"%{q}%"))
        )

    if bucket:
        stmt = stmt.where(*bucket_clauses(bucket))
    # Prompt 18: optional bill-date range (Dhaka dates) for the accounting dues report
    if date_from is not None:
        stmt = stmt.where(Invoice.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=DHAKA_TZ))
    if date_to is not None:
        stmt = stmt.where(Invoice.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=DHAKA_TZ))
    invoices = list(db.execute(stmt.limit(limit)).scalars().all())
    return [
        DueInvoiceSummary(
            invoice_id=inv.id,
            invoice_no=inv.invoice_no,
            patient_id=inv.patient_id,
            patient_code=inv.patient.patient_code,
            patient_name=inv.patient.name,
            patient_phone=inv.patient.phone,
            created_at=inv.created_at,
            net=inv.net,
            paid=inv.paid,
            due=inv.due,
            payment_status=inv.payment_status,
            age_days=due_age_days(inv),
            age_bucket=age_bucket(due_age_days(inv)),
            written_off=inv.written_off or 0,
        )
        for inv in invoices
    ]


def settle_invoice_due(
    db: Session,
    tenant_id: str,
    invoice_id: int,
    data: DueSettlementRequest,
    collector_id: int,
    acting_role: str = "RECEPTIONIST",
) -> Payment:
    """Collects payment against an invoice due balance and updates drawer state."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    if invoice.status == "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payments cannot be taken on a DRAFT invoice. Finalize it first.",
        )

    if invoice.due <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice has no outstanding due balance.",
        )

    if data.amount > invoice.due:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Overpayment is forbidden. Entered amount (Tk {data.amount}) exceeds due (Tk {invoice.due}).",
        )

    # Prompt 10E Part 4: backend channel list; OTHER requires the typed channel name
    method, channel_detail = validate_channel(data.method, data.channel_detail)
    data.method = method

    # Validate digital reference
    if data.method != "CASH":
        if not data.reference or len(data.reference.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction reference is required for payment method ({data.method}).",
            )
        clean_ref = data.reference.strip()
        dup = db.execute(
            select(Payment).where(
                Payment.tenant_id == tenant_id,
                Payment.reference == clean_ref,
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction reference '{clean_ref}' has already been used.",
            )

    # Prompt 18B: a payment needs an OPEN day (409 closed / reopened, 400 none ever opened)
    active_day = accounting_service.require_open_day(db, tenant_id)

    change_due = 0
    if data.method == "CASH" and data.cash_tendered:
        if data.cash_tendered > data.amount:
            change_due = data.cash_tendered - data.amount

    # Create Payment record
    pmt = Payment(
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        business_day_id=active_day.id if active_day else None,
        amount=data.amount,
        method=data.method,
        reference=data.reference.strip() if data.reference else None,
        channel_detail=channel_detail,
        change_amount=change_due,
        received_by_id=collector_id,
    )
    db.add(pmt)

    # Update Invoice balances
    before_due = invoice.due
    invoice.paid += data.amount
    invoice.due -= data.amount
    invoice.payment_status = "PAID" if invoice.due == 0 else "PARTLY_PAID"

    # Update active Day channel balance
    if active_day:
        add_to_channel_balance(db, tenant_id, active_day, data.method, data.amount)

    db.flush()
    accounting_service.post_payment_received(db, tenant_id, invoice, pmt, collector_id)  # Prompt 18

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="COLLECT_PATIENT_DUE",
        entity_type="INVOICE",
        entity_id=invoice.id,
        acting_role=acting_role,
        actor_id=collector_id,
        before_value=f"Due: Tk {before_due}",
        after_value=f"Paid: Tk {data.amount}, Remaining Due: Tk {invoice.due}, Method: {data.method}" + (f" ({channel_detail})" if channel_detail else ""),
    )
    return pmt


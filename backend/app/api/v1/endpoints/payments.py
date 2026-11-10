from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.models.payment import Payment
from backend.app.schemas.payment import (
    PaymentCreate,
    DueSettlementRequest,
    PaymentResponse,
    DueInvoiceSummary,
)
from backend.app.services.payment_service import (
    list_due_invoices,
    settle_invoice_due,
)

router = APIRouter()


class GenericPaymentRequest(PaymentCreate):
    channel: Optional[str] = None
    reference_no: Optional[str] = None
    notes: Optional[str] = None


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, summary="Create a payment / settle due")
@router.post("/payments/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, summary="Create a payment / settle due (alias)")
def create_payment(
    data: GenericPaymentRequest,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    method = data.channel or data.method or "CASH"
    ref = data.reference_no or data.reference
    due_req = DueSettlementRequest(
        amount=data.amount,
        method=method,
        reference=ref,
        cash_tendered=data.cash_tendered,
    )
    pmt = settle_invoice_due(
        db=db,
        tenant_id=actor.tenant_id,
        invoice_id=data.invoice_id,
        data=due_req,
        collector_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(pmt)
    return PaymentResponse(
        id=pmt.id,
        invoice_id=pmt.invoice_id,
        amount=pmt.amount,
        method=pmt.method,
        reference=pmt.reference,
        change_amount=pmt.change_amount,
        received_at=pmt.received_at,
        received_by_id=pmt.received_by_id,
        received_by_name=actor.display_name,
    )


@router.get("/dues", response_model=List[DueInvoiceSummary], summary="List patients with outstanding dues")
def get_dues(
    q: Optional[str] = Query(default=None, description="Search by invoice no, patient name, phone"),
    limit: int = Query(default=50, le=100),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return list_due_invoices(db, actor.tenant_id, query=q, limit=limit)


@router.post("/invoices/{invoice_id}/settle-due", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, summary="Settle or partially pay an outstanding invoice due")
def settle_due(
    invoice_id: int,
    data: DueSettlementRequest,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    pmt = settle_invoice_due(
        db=db,
        tenant_id=actor.tenant_id,
        invoice_id=invoice_id,
        data=data,
        collector_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(pmt)
    return PaymentResponse(
        id=pmt.id,
        invoice_id=pmt.invoice_id,
        amount=pmt.amount,
        method=pmt.method,
        reference=pmt.reference,
        change_amount=pmt.change_amount,
        received_at=pmt.received_at,
        received_by_id=pmt.received_by_id,
        received_by_name=actor.display_name,
    )


@router.get("/history", response_model=List[PaymentResponse], summary="View permitted payment history")
def get_payment_history(
    limit: int = Query(default=50, le=200),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Payment)
        .where(Payment.tenant_id == actor.tenant_id)
        .order_by(desc(Payment.received_at))
        .limit(limit)
    )
    pmts = list(db.execute(stmt).scalars().all())
    return [
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
        for p in pmts
    ]


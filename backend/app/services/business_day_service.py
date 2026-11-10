from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.app.models.business_day import BusinessDay, BusinessDayChannelBalance
from backend.app.models.payment import Payment
from backend.app.schemas.business_day import (
    BusinessDayStatusResponse,
    BusinessDayOpenRequest,
    BusinessDayChannelBalanceResponse,
)
from backend.app.services.audit_service import log_audit_event


STANDARD_CHANNELS = ["CASH", "BKASH", "NAGAD", "BANK_TRANSFER", "POS_CARD"]


def get_business_day_status(
    db: Session,
    tenant_id: str,
) -> BusinessDayStatusResponse:
    """Returns current active business day status and channel totals."""
    stmt = (
        select(BusinessDay)
        .where(
            BusinessDay.tenant_id == tenant_id,
            BusinessDay.status == "OPEN",
        )
    )
    active_day = db.execute(stmt).scalars().first()

    if not active_day:
        return BusinessDayStatusResponse(
            is_open=False,
            can_receptionist_open=True,
            can_receptionist_close=False,
            channels=[
                BusinessDayChannelBalanceResponse(channel=ch, opening_balance=0, received_amount=0)
                for ch in STANDARD_CHANNELS
            ],
        )

    # Compute live received total for this day session
    stmt_sum = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(
            Payment.tenant_id == tenant_id,
            Payment.business_day_id == active_day.id,
        )
    )
    live_received = db.execute(stmt_sum).scalar_one()

    channel_list = [
        BusinessDayChannelBalanceResponse(
            channel=cb.channel,
            opening_balance=cb.opening_balance,
            received_amount=cb.received_amount,
        )
        for cb in active_day.channel_balances
    ]

    return BusinessDayStatusResponse(
        is_open=True,
        current_business_day_id=active_day.id,
        day_number=active_day.day_number,
        opened_at=active_day.opened_at,
        opened_by_name=active_day.opened_by.display_name if active_day.opened_by else "Staff",
        opening_float=active_day.opening_float,
        total_received_today=live_received,
        channels=channel_list,
        can_receptionist_open=False,
        can_receptionist_close=False,  # Receptionist can NEVER close
    )


def open_business_day(
    db: Session,
    tenant_id: str,
    data: BusinessDayOpenRequest,
    opener_id: int,
    acting_role: str = "RECEPTIONIST",
) -> BusinessDay:
    """Opens a new business day session if none is currently active."""
    # Check if a day is already open
    existing = (
        db.execute(
            select(BusinessDay).where(
                BusinessDay.tenant_id == tenant_id,
                BusinessDay.status == "OPEN",
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Business Day #{existing.day_number} is already OPEN. Only one session may be open at a time.",
        )

    # Count previous days to assign next day_number
    count_stmt = select(func.count(BusinessDay.id)).where(BusinessDay.tenant_id == tenant_id)
    prev_count = db.execute(count_stmt).scalar_one()
    next_day_num = prev_count + 1

    b_day = BusinessDay(
        tenant_id=tenant_id,
        day_number=next_day_num,
        opened_by_id=opener_id,
        opening_float=data.opening_float,
        status="OPEN",
        notes=data.notes,
    )
    db.add(b_day)
    db.flush()

    # Initialize channel balances
    provided_balances = {item.channel: item.opening_balance for item in (data.channel_balances or [])}
    for ch in STANDARD_CHANNELS:
        open_bal = data.opening_float if ch == "CASH" else provided_balances.get(ch, 0)
        c_bal = BusinessDayChannelBalance(
            tenant_id=tenant_id,
            business_day_id=b_day.id,
            channel=ch,
            opening_balance=open_bal,
            received_amount=0,
        )
        db.add(c_bal)

    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="OPEN_BUSINESS_DAY",
        entity_type="BUSINESS_DAY",
        entity_id=b_day.id,
        acting_role=acting_role,
        actor_id=opener_id,
        after_value=f"Opened Session #{b_day.day_number}, Opening Cash Float: Tk {b_day.opening_float}",
    )
    return b_day


def reject_close_business_day_for_receptionist(
    acting_role: str,
):
    """Enforces Section 2.11 & 2.11-13: Receptionist and Cashier CANNOT close business day."""
    role_norm = acting_role.strip().upper() if acting_role else ""
    if role_norm not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied. Receptionists and Cashiers are strictly forbidden from closing, adjusting, or reconciling a Business Day. Closing requires Admin or Owner credentials.",
        )


def close_business_day(
    db: Session,
    tenant_id: str,
    closer_id: int,
    acting_role: str = "ADMIN",
    notes: Optional[str] = None,
) -> BusinessDay:
    """Closes the current active business day session. Strictly restricted to Admin/Owner."""
    reject_close_business_day_for_receptionist(acting_role)

    b_day = (
        db.execute(
            select(BusinessDay).where(
                BusinessDay.tenant_id == tenant_id,
                BusinessDay.status == "OPEN",
            )
        )
        .scalars()
        .first()
    )
    if not b_day:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Business Day session is currently open to close.",
        )

    b_day.status = "CLOSED"
    b_day.closed_at = datetime.utcnow()
    b_day.closed_by_id = closer_id
    if notes and notes.strip():
        b_day.notes = f"{b_day.notes or ''} [Closed: {notes.strip()}]".strip()

    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="CLOSE_BUSINESS_DAY",
        entity_type="BUSINESS_DAY",
        entity_id=b_day.id,
        acting_role=acting_role,
        actor_id=closer_id,
        after_value=f"Closed Business Day #{b_day.day_number} (Status: CLOSED)",
    )
    return b_day


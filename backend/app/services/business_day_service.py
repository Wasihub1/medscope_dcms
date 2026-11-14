from datetime import datetime
from typing import Optional
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


from backend.app.core.payment_channels import PAYMENT_CHANNELS, normalize_channel

# Prompt 10E Part 4: all backend channels (CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER)
STANDARD_CHANNELS = list(PAYMENT_CHANNELS)


def get_or_create_channel_balance(db: Session, tenant_id: str, day: BusinessDay, channel: str) -> BusinessDayChannelBalance:
    """Returns the day's balance row for a channel, creating a zero row when it is missing
    (business days opened before a channel existed, e.g. ROCKET / OTHER)."""
    ch = normalize_channel(channel)
    row = db.execute(
        select(BusinessDayChannelBalance).where(
            BusinessDayChannelBalance.business_day_id == day.id,
            BusinessDayChannelBalance.channel == ch,
        )
    ).scalar_one_or_none()
    if row is None:
        row = BusinessDayChannelBalance(
            tenant_id=tenant_id, business_day_id=day.id, channel=ch, opening_balance=0, received_amount=0
        )
        db.add(row)
        db.flush()
    return row


def add_to_channel_balance(db: Session, tenant_id: str, day: BusinessDay, channel: str, amount: int) -> None:
    """Adds (or, with a negative amount, removes) money received on a channel for the day."""
    row = get_or_create_channel_balance(db, tenant_id, day, channel)
    row.received_amount = max(0, row.received_amount + int(amount))


def get_business_day_state(db: Session, tenant_id: str):
    """Prompt 13B: non-financial open/closed state from the same query as get_business_day_status."""
    from backend.app.schemas.business_day import BusinessDayState
    day = db.execute(
        select(BusinessDay).where(BusinessDay.tenant_id == tenant_id, BusinessDay.status == "OPEN")
    ).scalars().first()
    if not day:
        return BusinessDayState(is_open=False)
    return BusinessDayState(is_open=True, day_number=day.day_number, business_date=day.opened_at.strftime("%Y-%m-%d"))


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
    # Prompt 10E: show every channel, even when the day was opened before it existed
    present = {cb.channel for cb in active_day.channel_balances}
    channel_list += [
        BusinessDayChannelBalanceResponse(channel=ch, opening_balance=0, received_amount=0)
        for ch in STANDARD_CHANNELS
        if ch not in present
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
                BusinessDay.status.in_(["OPEN", "REOPENED"]),
            )
        )
        .scalars()
        .first()
    )
    if existing:
        # Prompt 18B: only one day may be OPEN or REOPENED; a reopened day must be closed again first
        state = "already OPEN" if existing.status == "OPEN" else "REOPENED and must be closed again first"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Business Day #{existing.day_number} is {state}. Only one session may be open at a time.",
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

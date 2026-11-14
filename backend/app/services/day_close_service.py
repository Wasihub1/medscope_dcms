"""Prompt 18 (Module 22): day close, reopen and the day-screen money movements.

Expected cash (D45) = opening cash + cash collections - cash refunds - cash paid out, where cash paid out is the
bank deposits, owner withdrawals and small expenses entered on the day screen. Write-offs are not cash and are
not in the formula. Commission, visit-fee, consultant-fee and outside-lab payouts have no data source yet
(Modules 19 / 20 / 28), so they contribute 0 and are listed as such. Wallet / bank channels are checked on their
own lines. Variance = counted - expected; a reason is required when it exceeds the owner's tolerance
(tenant_settings: cash_variance_tolerance). The "no unsynced items" condition always passes: offline sync is not built.
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.payment_channels import PAYMENT_CHANNELS, normalize_channel
from backend.app.core.security import CurrentActor
from backend.app.core.timezone import utc_now
from backend.app.models.accounting import DayMovement, JournalEntry, JournalLine
from backend.app.models.business_day import BusinessDay, BusinessDayChannelBalance
from backend.app.models.payment import Payment
from backend.app.models.refund import RefundRequest
from backend.app.services import accounting_service as acct
from backend.app.services import settings_service
from backend.app.services.audit_service import log_audit_event
from backend.app.services.business_day_service import get_or_create_channel_balance

MOVEMENT_KINDS = ("BANK_DEPOSIT", "OWNER_WITHDRAWAL", "EXPENSE")
# Payouts that belong to modules not built yet: always 0 here, shown so the screen is not misleading.
DEFERRED_PAYOUTS = ("Commission payouts", "Visit-fee handover", "Consultant fees", "Outside-lab payments")


def _day(db: Session, tenant_id: str, day_id: int) -> BusinessDay:
    day = db.get(BusinessDay, day_id)
    if day is None or day.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business day not found.")
    return day


def _current_day(db: Session, tenant_id: str) -> Optional[BusinessDay]:
    """The day the screen works on: the OPEN day, else the most recent day (so a closed or reopened one is shown)."""
    day = acct.open_day(db, tenant_id)
    if day is not None:
        return day
    return db.execute(select(BusinessDay).where(BusinessDay.tenant_id == tenant_id).order_by(BusinessDay.id.desc())).scalars().first()


def _window_end(day: BusinessDay) -> datetime:
    return day.closed_at if (day.status in ("CLOSED", "REOPENED") and day.closed_at) else utc_now()


def compute_summary(db: Session, tenant_id: str, day: BusinessDay) -> dict:
    """Pure read: opening, collections, refunds, movements, expected, counted and variance per channel."""
    end = _window_end(day)
    collections: Dict[str, int] = {ch: 0 for ch in PAYMENT_CHANNELS}
    for method, total in db.execute(
        select(Payment.method, func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.tenant_id == tenant_id, Payment.business_day_id == day.id).group_by(Payment.method)
    ):
        ch = normalize_channel(method)
        collections[ch if ch in collections else "OTHER"] += int(total)
    refunds: Dict[str, int] = {ch: 0 for ch in PAYMENT_CHANNELS}
    for method, total in db.execute(
        select(RefundRequest.disbursement_method, func.coalesce(func.sum(RefundRequest.amount), 0))
        .where(RefundRequest.tenant_id == tenant_id, RefundRequest.status == "DISBURSED",
               RefundRequest.disbursed_at >= day.opened_at, RefundRequest.disbursed_at <= end)
        .group_by(RefundRequest.disbursement_method)
    ):
        ch = normalize_channel(method)
        refunds[ch if ch in refunds else "OTHER"] += int(total)
    moves = {k: 0 for k in MOVEMENT_KINDS}
    for kind, total in db.execute(
        select(DayMovement.kind, func.coalesce(func.sum(DayMovement.amount), 0))
        .where(DayMovement.business_day_id == day.id).group_by(DayMovement.kind)
    ):
        moves[kind] = int(total)
    bal = {b.channel: b for b in db.execute(select(BusinessDayChannelBalance).where(BusinessDayChannelBalance.business_day_id == day.id)).scalars()}

    # Prompt 18B: adjusting entries posted while the day was reopened move the channel account but are not in the source
    # tables, so they are added explicitly. Variance entries (and their reversals) are excluded: they are the count mechanism.
    ids = acct.ensure_accounts(db, tenant_id)
    var_entries = select(JournalLine.entry_id).where(JournalLine.account_id == ids["CASH_VARIANCE"])
    adjustments: Dict[str, int] = {ch: 0 for ch in PAYMENT_CHANNELS}
    for ch in PAYMENT_CHANNELS:
        adjustments[ch] = int(db.execute(
            select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalEntry.business_day_id == day.id, JournalEntry.is_adjustment.is_(True),
                   JournalLine.account_id == ids[ch], JournalLine.entry_id.not_in(var_entries))
        ).scalar_one())
    channels: List[dict] = []
    for ch in PAYMENT_CHANNELS:
        opening = day.opening_float if ch == "CASH" else (bal[ch].opening_balance if ch in bal else 0)
        paid_out = sum(moves.values()) if ch == "CASH" else 0
        expected = opening + collections[ch] - refunds[ch] - paid_out + adjustments[ch]
        row = bal.get(ch)
        channels.append({
            "channel": ch, "opening": opening, "collections": collections[ch], "refunds": refunds[ch],
            "paid_out": paid_out, "adjustments": adjustments[ch], "expected": expected,
            "counted": row.closing_counted if row else None, "variance": row.variance if row else None,
        })
    return {
        "channels": channels,
        "cash": {
            "opening_cash": day.opening_float, "cash_collections": collections["CASH"], "cash_refunds": refunds["CASH"],
            "adjusting_entries": adjustments["CASH"], "bank_deposits": moves["BANK_DEPOSIT"], "owner_withdrawals": moves["OWNER_WITHDRAWAL"], "expenses": moves["EXPENSE"],
            "deferred_payouts": {name: 0 for name in DEFERRED_PAYOUTS},
            "expected_cash": channels[0]["expected"],
        },
    }


def get_day_screen(db: Session, tenant_id: str) -> dict:
    day = _current_day(db, tenant_id)
    tolerance = settings_service.get_int(db, tenant_id, "cash_variance_tolerance")
    if day is None:
        return {"day": None, "tolerance": tolerance, "unsynced_items": 0}
    summary = compute_summary(db, tenant_id, day)
    movements = db.execute(select(DayMovement).where(DayMovement.business_day_id == day.id).order_by(DayMovement.id)).scalars().all()
    return {
        "day": {
            "id": day.id, "day_number": day.day_number, "status": day.status, "opened_at": day.opened_at, "closed_at": day.closed_at,
            "opening_cash": day.opening_float, "counted_cash": day.closing_cash_counted, "variance": day.closing_variance,
            "variance_reason": day.variance_reason, "reopen_reason": day.reopen_reason, "reopened_at": day.reopened_at,
        },
        "tolerance": tolerance,
        "unsynced_items": 0,  # offline sync is not built: this condition always passes
        **summary,
        "movements": [{"id": m.id, "kind": m.kind, "amount": m.amount, "note": m.note, "created_at": m.created_at} for m in movements],
    }


def record_movement(db: Session, actor: CurrentActor, kind: str, amount: int, note: Optional[str]) -> dict:
    """Bank deposit / owner withdrawal / small expense. Cash leaves the open day's drawer and the journal is posted."""
    if kind not in MOVEMENT_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown movement '{kind}'.")
    if kind == "OWNER_WITHDRAWAL" and actor.role != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the Owner can record an owner withdrawal.")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The amount must be a whole number of Taka above 0.")
    text = (note or "").strip() or None
    if kind == "EXPENSE" and not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Say what the expense was for.")
    day = acct.open_day(db, actor.tenant_id)
    if day is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No business day is open. Open the day first.")
    cash_now = compute_summary(db, actor.tenant_id, day)["cash"]["expected_cash"]
    if amount > cash_now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Only Tk {cash_now} of cash should be in the drawer; Tk {amount} cannot be taken out.")
    mv = DayMovement(tenant_id=actor.tenant_id, business_day_id=day.id, kind=kind, amount=amount, note=text, created_by_id=actor.id)
    db.add(mv)
    db.flush()
    entry = acct.post_day_movement(db, actor.tenant_id, day, mv, actor.id)
    mv.journal_entry_id = entry.id
    log_audit_event(db=db, tenant_id=actor.tenant_id, action=f"DAY_{kind}", entity_type="BUSINESS_DAY", entity_id=day.id,
                    acting_role=actor.role, actor_id=actor.id, after_value=f"{kind} Tk {amount}" + (f": {text}" if text else ""))
    db.flush()
    return {"id": mv.id, "kind": kind, "amount": amount, "journal_entry_id": entry.id}


def _posted_variance(db: Session, day: BusinessDay, channel: str) -> int:
    """Net variance already in the journal for this day and channel (counted - expected): the movement of the channel
    account inside the day's entries that also touch Cash variance (the variance entries and any reversal of them)."""
    ids = acct.ensure_accounts(db, day.tenant_id)
    var_entries = select(JournalLine.entry_id).join(JournalEntry, JournalEntry.id == JournalLine.entry_id).where(
        JournalEntry.business_day_id == day.id, JournalLine.account_id == ids["CASH_VARIANCE"])
    return int(db.execute(
        select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .where(JournalLine.entry_id.in_(var_entries), JournalLine.account_id == ids[acct.channel_key(channel)])
    ).scalar_one())


def close_day(db: Session, actor: CurrentActor, counted: Dict[str, int], reason: Optional[str], notes: Optional[str], day_id: Optional[int] = None) -> BusinessDay:
    """Closes the OPEN day, or (with day_id) re-closes a REOPENED one. `counted` must hold CASH; other channels are optional."""
    if day_id is not None:
        day = _day(db, actor.tenant_id, day_id)
        if day.status not in ("OPEN", "REOPENED"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Business Day #{day.day_number} is already closed.")
    else:
        day = acct.open_day(db, actor.tenant_id)
        if day is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active Business Day session is currently open to close.")
    reclose = day.status == "REOPENED"
    clean = {normalize_channel(k): v for k, v in (counted or {}).items()}
    if "CASH" not in clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Counted cash is required to close the day.")
    for ch, v in clean.items():
        if ch not in PAYMENT_CHANNELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown channel '{ch}'.")
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Counted amount for {ch} must be a whole number of Taka, 0 or more.")
    summary = compute_summary(db, actor.tenant_id, day)
    by_ch = {c["channel"]: c for c in summary["channels"]}
    variances = {ch: v - by_ch[ch]["expected"] for ch, v in clean.items()}
    tolerance = settings_service.get_int(db, actor.tenant_id, "cash_variance_tolerance")
    text = (reason or "").strip() or None
    if any(abs(v) > tolerance for v in variances.values()) and not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"A reason is required: a variance exceeds the tolerance of Tk {tolerance}.")

    now = utc_now()
    for ch, v in clean.items():
        row = get_or_create_channel_balance(db, actor.tenant_id, day, ch)
        row.closing_counted, row.variance = v, variances[ch]
        # Journal: post only what is not already posted (a re-close after a reopen posts the difference as an adjustment).
        delta = variances[ch] - (_posted_variance(db, day, ch) if reclose else 0)
        if delta:
            acct.post_cash_variance(db, actor.tenant_id, day, ch, delta, actor.id, is_adjustment=reclose)
    day.status = "CLOSED"
    if not reclose:
        day.closed_at = now  # a re-close keeps the original close time, so the day's time window never grows
    day.closed_by_id = actor.id
    day.closing_cash_counted = clean["CASH"]
    day.closing_expected_cash = by_ch["CASH"]["expected"]
    day.closing_variance = variances["CASH"]
    day.variance_reason = text
    if notes and notes.strip():
        day.notes = f"{day.notes or ''} [Closed: {notes.strip()}]".strip()
    log_audit_event(db=db, tenant_id=actor.tenant_id, action="CLOSE_BUSINESS_DAY", entity_type="BUSINESS_DAY", entity_id=day.id,
                    acting_role=actor.role, actor_id=actor.id,
                    after_value=f"{'Re-closed' if reclose else 'Closed'} Business Day #{day.day_number}: expected cash Tk {by_ch['CASH']['expected']}, "
                                f"counted Tk {clean['CASH']}, variance Tk {variances['CASH']:+d}" + (f". Reason: {text}" if text else ""))
    db.flush()
    return day


def reopen_day(db: Session, actor: CurrentActor, day_id: int, reason: Optional[str]) -> BusinessDay:
    """Owner only, reason required. The day takes adjusting entries only (no payments, no new movements)."""
    if actor.role != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the Owner can reopen a closed day.")
    text = (reason or "").strip()
    if len(text) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to reopen a closed day.")
    day = _day(db, actor.tenant_id, day_id)
    if day.status != "CLOSED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Business Day #{day.day_number} is {day.status}; only a closed day can be reopened.")
    day.status, day.reopened_at, day.reopened_by_id, day.reopen_reason = "REOPENED", utc_now(), actor.id, text[:300]
    log_audit_event(db=db, tenant_id=actor.tenant_id, action="REOPEN_BUSINESS_DAY", entity_type="BUSINESS_DAY", entity_id=day.id,
                    acting_role=actor.role, actor_id=actor.id,
                    after_value=f"Reopened Business Day #{day.day_number} for adjusting entries only. Reason: {text}")
    db.flush()
    return day


def post_adjustment(db: Session, actor: CurrentActor, day_id: int, reverse_entry_id: Optional[int], lines: Optional[list], reason: Optional[str]) -> JournalEntry:
    """Adjusting entry on a REOPENED day: either the reversal of an existing entry of that day, or a manual
    balanced entry between chart accounts. Owner only, reason required. Nothing already posted is edited."""
    if actor.role != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the Owner can post an adjusting entry.")
    text = (reason or "").strip()
    if len(text) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required for an adjusting entry.")
    day = _day(db, actor.tenant_id, day_id)
    if day.status != "REOPENED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Adjusting entries can only be posted to a reopened day.")
    if reverse_entry_id is not None:
        orig = db.get(JournalEntry, reverse_entry_id)
        if orig is None or orig.tenant_id != actor.tenant_id or orig.business_day_id != day.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That entry does not belong to this day.")
        entry = acct.reverse_entry(db, actor.tenant_id, reverse_entry_id, actor.id, f"Adjustment: {text}")
    else:
        if not lines or len(lines) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An adjusting entry needs at least two lines.")
        parsed = []
        for l in lines:
            key = str(l.get("account", "")).upper()
            if key not in acct.CHART:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown account '{key}'.")
            d, c = int(l.get("debit", 0) or 0), int(l.get("credit", 0) or 0)
            if d < 0 or c < 0 or (d and c) or not (d or c):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each line needs a positive debit or a positive credit, not both.")
            parsed.append((key, d, c))
        if sum(p[1] for p in parsed) != sum(p[2] for p in parsed):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debits must equal credits.")
        entry = acct.post(db, actor.tenant_id, "ADJUSTMENT", parsed, actor_id=actor.id, source_type="BUSINESS_DAY", source_id=day.id,
                          business_day_id=day.id, is_adjustment=True, memo=f"Adjustment: {text}")
    log_audit_event(db=db, tenant_id=actor.tenant_id, action="POST_ADJUSTING_ENTRY", entity_type="BUSINESS_DAY", entity_id=day.id,
                    acting_role=actor.role, actor_id=actor.id, after_value=f"Adjusting entry #{entry.id} on reopened Business Day #{day.day_number}. Reason: {text}")
    db.flush()
    return entry

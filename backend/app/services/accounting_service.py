"""Prompt 18 (Module 21): double-entry journal. Every posting is a balanced entry (debits = credits); entries are
append-only (a database trigger blocks UPDATE / DELETE) and a mistake is fixed by a reversing entry.

Only events that really happen in the system today are posted: bill confirmed, payment received, line cancelled
(refund owed), refund paid, due written off, cash variance, bank deposit, owner withdrawal, small expense.
Commission, visit-fee handover, consultant fee and outside-lab cost are NOT posted: Modules 19 / 20 / 28 are not
built, so those events cannot happen yet.
"""
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.payment_channels import normalize_channel
from backend.app.core.timezone import to_dhaka_time, utc_now
from backend.app.models.accounting import Account, JournalEntry, JournalLine
from backend.app.models.business_day import BusinessDay

# key -> (code, name, type). Payment channels map to their own asset account; BANK_TRANSFER is the center's bank.
CHART: Dict[str, Tuple[str, str, str]] = {
    "CASH": ("1010", "Cash in hand", "ASSET"),
    "BKASH": ("1020", "bKash balance", "ASSET"),
    "NAGAD": ("1030", "Nagad balance", "ASSET"),
    "ROCKET": ("1040", "Rocket balance", "ASSET"),
    "POS_CARD": ("1050", "Card (POS) balance", "ASSET"),
    "BANK_TRANSFER": ("1060", "Bank", "ASSET"),
    "OTHER": ("1070", "Other channel balance", "ASSET"),
    "RECEIVABLE": ("1200", "Patient receivable", "ASSET"),
    "REFUND_PAYABLE": ("2100", "Refunds payable", "LIABILITY"),
    "OWNER_DRAWINGS": ("3100", "Owner drawings", "EQUITY"),
    "TEST_REVENUE": ("4000", "Test revenue", "REVENUE"),
    "URGENT_REVENUE": ("4010", "Urgent fee revenue", "REVENUE"),
    "DISCOUNT": ("4900", "Discount given", "REVENUE"),  # contra-revenue: carries a debit balance
    "OPERATING_EXPENSE": ("5000", "Operating expense", "EXPENSE"),
    "BAD_DEBT": ("5100", "Bad debt (written-off dues)", "EXPENSE"),
    "CASH_VARIANCE": ("5200", "Cash variance", "EXPENSE"),
}
CHANNEL_KEYS = ("CASH", "BKASH", "NAGAD", "ROCKET", "POS_CARD", "BANK_TRANSFER", "OTHER")

Line = Tuple[str, int, int]  # (account key, debit, credit)


def ensure_accounts(db: Session, tenant_id: str) -> Dict[str, int]:
    """Returns {key: account id}, creating any missing account of the chart for this tenant (idempotent)."""
    rows = {a.code: a for a in db.execute(select(Account).where(Account.tenant_id == tenant_id)).scalars()}
    created = False
    for _key, (code, name, typ) in CHART.items():
        if code not in rows:
            acc = Account(tenant_id=tenant_id, code=code, name=name, type=typ)
            db.add(acc)
            rows[code] = acc
            created = True
    if created:
        db.flush()
    return {key: rows[code].id for key, (code, _n, _t) in CHART.items()}


def channel_key(method: Optional[str]) -> str:
    ch = normalize_channel(method)
    return ch if ch in CHANNEL_KEYS else "OTHER"


def local_today() -> date:
    return to_dhaka_time(utc_now()).date()


def open_day(db: Session, tenant_id: str) -> Optional[BusinessDay]:
    return db.execute(select(BusinessDay).where(BusinessDay.tenant_id == tenant_id, BusinessDay.status == "OPEN")).scalars().first()


def require_open_day(db: Session, tenant_id: str) -> BusinessDay:
    """Prompt 18B: cash-affecting actions (payment, bill confirmation, cash refund) need an OPEN day. 'No OPEN day'
    is never treated as 'no day tracking': a CLOSED or REOPENED day answers 409, no day at all answers 400."""
    day = open_day(db, tenant_id)
    if day is not None:
        return day
    last = db.execute(select(BusinessDay).where(BusinessDay.tenant_id == tenant_id).order_by(BusinessDay.id.desc())).scalars().first()
    if last is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No business day has been opened. Open the day before taking money or confirming a bill.")
    raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                        detail=f"Business Day #{last.day_number} is {last.status.lower()}; no day is open. Open a new day before taking money or confirming a bill (a closed day cannot be edited).")


def post(
    db: Session,
    tenant_id: str,
    event_type: str,
    lines: Iterable[Line],
    *,
    actor_id: Optional[int],
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    memo: Optional[str] = None,
    business_day_id: Optional[int] = None,
    reverses_entry_id: Optional[int] = None,
    is_adjustment: bool = False,
) -> Optional[JournalEntry]:
    """Posts one balanced entry in the caller's transaction (the caller commits). Zero lines are dropped; an
    entry with no money returns None. A closed day takes no ordinary entry: only an adjusting entry may be
    posted to a REOPENED day (Module 22, D47)."""
    clean = [(k, int(d), int(c)) for k, d, c in lines if int(d) or int(c)]
    if not clean:
        return None
    if sum(d for _k, d, _c in clean) != sum(c for _k, _d, c in clean):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Journal entry '{event_type}' does not balance (debits must equal credits).")
    if any(d < 0 or c < 0 or (d and c) for _k, d, c in clean):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="A journal line must carry a positive debit or a positive credit, not both.")
    if business_day_id is not None:
        day = db.get(BusinessDay, business_day_id)
        if day is None or day.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business day not found.")
        if day.status == "CLOSED" or (day.status == "REOPENED" and not is_adjustment):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Business Day #{day.day_number} is closed. A closed day cannot be edited; the Owner can reopen it and post adjusting entries only.")
    ids = ensure_accounts(db, tenant_id)
    entry = JournalEntry(
        tenant_id=tenant_id, entry_date=local_today(), business_day_id=business_day_id, event_type=event_type,
        source_type=source_type, source_id=source_id, memo=(memo[:300] if memo else None),
        reverses_entry_id=reverses_entry_id, is_adjustment=is_adjustment, created_by_id=actor_id,
    )
    db.add(entry)
    db.flush()
    for key, d, c in clean:
        db.add(JournalLine(tenant_id=tenant_id, entry_id=entry.id, account_id=ids[key], debit=d, credit=c))
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# Real postings (called from the existing flows; none of them changes that flow's own logic)
# ---------------------------------------------------------------------------
def post_bill_confirmed(db: Session, invoice, actor_id: Optional[int], business_day_id: Optional[int]) -> None:
    """Dr Patient receivable (net) + Dr Discount given; Cr Test revenue (gross) + Cr Urgent fee revenue.
    net = gross - discount + urgent fee, so the entry balances. No visit-fee line exists in the system today."""
    post(db, invoice.tenant_id, "BILL_CONFIRMED",
         [("RECEIVABLE", invoice.net, 0), ("DISCOUNT", invoice.discount, 0),
          ("TEST_REVENUE", 0, invoice.gross), ("URGENT_REVENUE", 0, invoice.urgent_fee or 0)],
         actor_id=actor_id, source_type="INVOICE", source_id=invoice.id, business_day_id=business_day_id,
         memo=f"Bill {invoice.invoice_no} confirmed")


def post_payment_received(db: Session, tenant_id: str, invoice, payment, actor_id: Optional[int]) -> None:
    post(db, tenant_id, "PAYMENT_RECEIVED",
         [(channel_key(payment.method), payment.amount, 0), ("RECEIVABLE", 0, payment.amount)],
         actor_id=actor_id, source_type="PAYMENT", source_id=payment.id, business_day_id=payment.business_day_id,
         memo=f"Payment on bill {invoice.invoice_no} via {channel_key(payment.method)}")


def post_line_cancelled(db: Session, invoice, line, net_before: int, refund_amount: int, actor_id: Optional[int]) -> None:
    """Reverses the cancelled line's revenue (the existing cancellation logic already lowered invoice.net).
    Cr Receivable by the net reduction; the rest of the price is the discount that no longer applies. A refund owed
    to the patient moves from the receivable to Refunds payable (paid later by post_refund_disbursed)."""
    net_drop = max(0, net_before - invoice.net)
    gap = line.unit_price_snapshot - net_drop  # >= 0: price not recovered from the receivable was discount
    lines: List[Line] = [("TEST_REVENUE", line.unit_price_snapshot, 0), ("RECEIVABLE", 0, net_drop)]
    lines.append(("DISCOUNT", 0, gap) if gap >= 0 else ("DISCOUNT", -gap, 0))
    lines += [("RECEIVABLE", refund_amount, 0), ("REFUND_PAYABLE", 0, refund_amount)]
    day = open_day(db, invoice.tenant_id)
    post(db, invoice.tenant_id, "LINE_CANCELLED", lines, actor_id=actor_id, source_type="INVOICE_LINE", source_id=line.id,
         business_day_id=day.id if day else None, memo=f"Line {line.test_code_snapshot} on bill {invoice.invoice_no} cancelled")


def post_refund_disbursed(db: Session, tenant_id: str, req, channel: str, actor_id: Optional[int]) -> None:
    day = open_day(db, tenant_id)
    post(db, tenant_id, "REFUND_PAID", [("REFUND_PAYABLE", req.amount, 0), (channel_key(channel), 0, req.amount)],
         actor_id=actor_id, source_type="REFUND", source_id=req.id, business_day_id=day.id if day else None,
         memo=f"Refund paid via {channel_key(channel)}")


def post_due_written_off(db: Session, tenant_id: str, invoice, writeoff, actor_id: Optional[int]) -> None:
    """Dr Bad debt, Cr Patient receivable. Not a discount and not cash."""
    day = open_day(db, tenant_id)
    post(db, tenant_id, "DUE_WRITTEN_OFF", [("BAD_DEBT", writeoff.amount, 0), ("RECEIVABLE", 0, writeoff.amount)],
         actor_id=actor_id, source_type="WRITEOFF", source_id=writeoff.id, business_day_id=day.id if day else None,
         memo=f"Due written off on bill {invoice.invoice_no}")


def post_cash_variance(db: Session, tenant_id: str, day: BusinessDay, channel: str, variance: int, actor_id: Optional[int], is_adjustment: bool) -> None:
    """variance = counted - expected. Shortage: Dr Cash variance, Cr channel. Overage: Dr channel, Cr Cash variance."""
    key = channel_key(channel)
    lines: List[Line] = [("CASH_VARIANCE", -variance, 0), (key, 0, -variance)] if variance < 0 else [(key, variance, 0), ("CASH_VARIANCE", 0, variance)]
    post(db, tenant_id, "CASH_VARIANCE", lines, actor_id=actor_id, source_type="BUSINESS_DAY", source_id=day.id,
         business_day_id=day.id, is_adjustment=is_adjustment, memo=f"Day #{day.day_number} {key} variance {variance:+d}")


MOVEMENT_LINES = {
    "BANK_DEPOSIT": ("BANK_TRANSFER", "CASH"),       # Dr Bank, Cr Cash
    "OWNER_WITHDRAWAL": ("OWNER_DRAWINGS", "CASH"),  # Dr Owner drawings, Cr Cash
    "EXPENSE": ("OPERATING_EXPENSE", "CASH"),        # Dr Operating expense, Cr Cash
}


def post_day_movement(db: Session, tenant_id: str, day: BusinessDay, movement, actor_id: Optional[int]) -> JournalEntry:
    debit_key, credit_key = MOVEMENT_LINES[movement.kind]
    return post(db, tenant_id, movement.kind, [(debit_key, movement.amount, 0), (credit_key, 0, movement.amount)],
                actor_id=actor_id, source_type="DAY_MOVEMENT", source_id=movement.id, business_day_id=day.id, memo=movement.note)


def reverse_entry(db: Session, tenant_id: str, entry_id: int, actor_id: Optional[int], memo: Optional[str]) -> JournalEntry:
    """A reversal is a NEW entry with the debits and credits swapped, referencing the original."""
    orig = db.execute(select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.tenant_id == tenant_id).with_for_update()).scalar_one_or_none()
    if orig is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    if orig.reverses_entry_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A reversing entry cannot itself be reversed; post a new entry instead.")
    if db.execute(select(JournalEntry.id).where(JournalEntry.reverses_entry_id == orig.id)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This entry has already been reversed.")
    ids = {v: k for k, v in ensure_accounts(db, tenant_id).items()}
    swapped = [(ids[l.account_id], l.credit, l.debit) for l in orig.lines]
    return post(db, tenant_id, "REVERSAL", swapped, actor_id=actor_id, source_type="JOURNAL_ENTRY", source_id=orig.id,
                business_day_id=orig.business_day_id, reverses_entry_id=orig.id, is_adjustment=True,
                memo=(memo or f"Reversal of entry #{orig.id}"))

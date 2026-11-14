"""Prompt 18 (Module 21): the four V1 accounting reports, read from the journal (plus the existing dues data).
Figures are on the date the entry was posted (Dhaka date); a flexible from / to range, no fiscal year.
Reports are read-only and never write."""
import csv
import io
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, JournalEntry, JournalLine
from backend.app.models.invoice import Invoice
from backend.app.models.referrer import Referrer
from backend.app.services import accounting_service as acct
from backend.app.services.payment_service import list_due_invoices


def _lines(tenant_id: str, date_from: Optional[date], date_to: Optional[date]):
    stmt = (
        select(JournalEntry.id, JournalEntry.entry_date, JournalEntry.event_type, JournalEntry.memo,
               Account.code, Account.name, Account.type, JournalLine.debit, JournalLine.credit, JournalLine.referrer_id)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, Account.id == JournalLine.account_id)
        .where(JournalEntry.tenant_id == tenant_id)
        .order_by(JournalEntry.entry_date, JournalEntry.id, JournalLine.id)
    )
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    return stmt


def cash_book(db: Session, tenant_id: str, date_from: Optional[date], date_to: Optional[date], channel: str = "CASH") -> dict:
    """Every movement on one money account (default Cash in hand) with a running balance."""
    code = acct.CHART[acct.channel_key(channel)][0]
    opening = 0
    if date_from:
        opening = db.execute(
            select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id).join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.tenant_id == tenant_id, Account.code == code, JournalEntry.entry_date < date_from)
        ).scalar_one()
    rows, running = [], int(opening)
    for eid, d, ev, memo, c, _n, _t, dr, cr, _r in db.execute(_lines(tenant_id, date_from, date_to).where(Account.code == code)):
        running += dr - cr
        rows.append({"date": d.isoformat(), "entry_id": eid, "event": ev, "memo": memo, "money_in": dr, "money_out": cr, "balance": running})
    return {"channel": acct.channel_key(channel), "account": acct.CHART[acct.channel_key(channel)][1], "from": date_from, "to": date_to,
            "opening_balance": int(opening), "total_in": sum(r["money_in"] for r in rows), "total_out": sum(r["money_out"] for r in rows),
            "closing_balance": running, "rows": rows}


def income_expense(db: Session, tenant_id: str, date_from: Optional[date], date_to: Optional[date]) -> dict:
    """Per day: income = revenue accounts (test + urgent fee, less discount given); expense = expense accounts
    (operating expense, bad debt, cash variance). Billing basis (the day the bill is confirmed), not cash received."""
    days: Dict[str, dict] = {}
    for _e, d, _ev, _m, code, _n, typ, dr, cr, _r in db.execute(_lines(tenant_id, date_from, date_to)):
        if typ not in ("REVENUE", "EXPENSE"):
            continue
        row = days.setdefault(d.isoformat(), {"date": d.isoformat(), "test_revenue": 0, "urgent_fee_revenue": 0, "discount_given": 0,
                                              "operating_expense": 0, "bad_debt": 0, "cash_variance": 0})
        net = cr - dr
        if code == "4000": row["test_revenue"] += net
        elif code == "4010": row["urgent_fee_revenue"] += net
        elif code == "4900": row["discount_given"] += -net  # shown as a positive amount given away
        elif code == "5000": row["operating_expense"] += -net
        elif code == "5100": row["bad_debt"] += -net
        elif code == "5200": row["cash_variance"] += -net
    rows = []
    for key in sorted(days):
        r = days[key]
        r["income"] = r["test_revenue"] + r["urgent_fee_revenue"] - r["discount_given"]
        r["expense"] = r["operating_expense"] + r["bad_debt"] + r["cash_variance"]
        r["net"] = r["income"] - r["expense"]
        rows.append(r)
    tot = {k: sum(r[k] for r in rows) for k in ("test_revenue", "urgent_fee_revenue", "discount_given", "income", "operating_expense", "bad_debt", "cash_variance", "expense", "net")}
    return {"from": date_from, "to": date_to, "rows": rows, "totals": tot}


def dues_report(db: Session, tenant_id: str, date_from: Optional[date], date_to: Optional[date]) -> dict:
    """Reuses the existing dues list (Prompt 17), filtered by bill date."""
    items = list_due_invoices(db, tenant_id, None, limit=100000, date_from=date_from, date_to=date_to)
    rows = [{"bill_no": i.invoice_no, "bill_date": i.created_at.date().isoformat(), "patient_code": i.patient_code, "patient": i.patient_name,
             "phone": i.patient_phone, "net": i.net, "paid": i.paid, "written_off": i.written_off, "due": i.due,
             "age_days": i.age_days, "age_bucket": i.age_bucket} for i in items]
    return {"from": date_from, "to": date_to, "rows": rows, "total_due": sum(r["due"] for r in rows)}


def cost_by_referrer(db: Session, tenant_id: str, date_from: Optional[date], date_to: Optional[date]) -> dict:
    """Billing per referrer (real) next to the cost booked against the referrer. Commission is not built (Module 19),
    so no journal line carries a referrer yet and every cost figure is 0; the report says so instead of faking figures."""
    stmt = (select(Referrer.id, Referrer.name, func.count(Invoice.id), func.coalesce(func.sum(Invoice.net), 0))
            .join(Invoice, Invoice.referrer_id == Referrer.id)
            .where(Invoice.tenant_id == tenant_id, Invoice.status.not_in(["DRAFT", "CANCELLED"])).group_by(Referrer.id, Referrer.name).order_by(Referrer.name))
    if date_from:
        stmt = stmt.where(func.date(func.timezone("Asia/Dhaka", Invoice.created_at)) >= date_from)
    if date_to:
        stmt = stmt.where(func.date(func.timezone("Asia/Dhaka", Invoice.created_at)) <= date_to)
    cost: Dict[int, int] = {}
    cstmt = (select(JournalLine.referrer_id, JournalLine.debit, JournalLine.credit)
             .join(JournalEntry, JournalEntry.id == JournalLine.entry_id).join(Account, Account.id == JournalLine.account_id)
             .where(JournalEntry.tenant_id == tenant_id, JournalLine.referrer_id.is_not(None), Account.type == "EXPENSE"))
    if date_from:
        cstmt = cstmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        cstmt = cstmt.where(JournalEntry.entry_date <= date_to)
    for rid, dr, cr in db.execute(cstmt):
        cost[rid] = cost.get(rid, 0) + dr - cr
    rows = [{"referrer_id": rid, "referrer": name, "bills": n, "net_billed": int(net), "cost": cost.get(rid, 0)} for rid, name, n, net in db.execute(stmt)]
    return {"from": date_from, "to": date_to, "rows": rows, "total_cost": sum(r["cost"] for r in rows),
            "note": "Commission (Module 19) is not built, so no cost is booked against any referrer yet; cost is 0 until it is."}


def journal(db: Session, tenant_id: str, date_from: Optional[date], date_to: Optional[date], business_day_id: Optional[int] = None, limit: int = 500) -> dict:
    stmt = select(JournalEntry).where(JournalEntry.tenant_id == tenant_id).order_by(JournalEntry.id.desc()).limit(limit)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    if business_day_id:
        stmt = stmt.where(JournalEntry.business_day_id == business_day_id)
    names = {v: k for k, v in acct.ensure_accounts(db, tenant_id).items()}
    out = []
    for e in db.execute(stmt).scalars():
        out.append({"id": e.id, "date": e.entry_date.isoformat(), "event": e.event_type, "memo": e.memo, "business_day_id": e.business_day_id,
                    "reverses_entry_id": e.reverses_entry_id, "is_adjustment": e.is_adjustment,
                    "lines": [{"account": names[l.account_id], "debit": l.debit, "credit": l.credit} for l in e.lines]})
    return {"entries": out}


def to_csv(rows: List[dict], columns: List[str]) -> str:
    """Excel-friendly CSV (UTF-8 with BOM); no export mechanism existed in the app, so this is the one."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c, "") for c in columns])
    return "﻿" + buf.getvalue()

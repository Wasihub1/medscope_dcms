"""
MedScope DCMS - Module 18 (Prompt 17): patient dues aging, call list, write-off (D11) and doctor balances (D43).

Dues stay derived from bills and payments (invoices.due is maintained by payments / refunds / write-offs;
nothing here lets anyone type a due). A write-off is a separate bad-debt record (due_writeoffs) and never
changes invoices.discount. No journal entries are posted (Module 21 is not built).
"""
from collections import defaultdict
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.security import CurrentActor
from backend.app.core.timezone import utc_now
from backend.app.models.dues import DoctorBalanceEntry, DueWriteOff
from backend.app.models.invoice import Invoice
from backend.app.models.patient import Patient
from backend.app.models.referrer import Referrer
from backend.app.models.user import Staff
from backend.app.services import accounting_service, settings_service
from backend.app.services.audit_service import log_audit_event

BUCKETS = ("0-7", "8-30", "31-90", "90+")
WRITEOFF_ROLES = ("ADMIN", "OWNER")


def age_bucket(days: int) -> str:
    if days <= 7:
        return "0-7"
    if days <= 30:
        return "8-30"
    if days <= 90:
        return "31-90"
    return "90+"


def bucket_clauses(bucket: str):
    """SQL conditions on invoices.created_at equal to age_bucket(): whole days since the bill."""
    if bucket not in BUCKETS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"bucket must be one of {', '.join(BUCKETS)}.")
    from datetime import timedelta
    now = utc_now()
    lo, hi = {"0-7": (0, 7), "8-30": (8, 30), "31-90": (31, 90), "90+": (91, None)}[bucket]
    clauses = [Invoice.created_at <= now - timedelta(days=lo)]
    if hi is not None:
        clauses.append(Invoice.created_at > now - timedelta(days=hi + 1))
    return clauses


def due_age_days(inv: Invoice) -> int:
    return max(0, (utc_now() - inv.created_at).days)


def _open_dues(tenant_id: str):
    return select(Invoice).join(Invoice.patient).where(
        Invoice.tenant_id == tenant_id, Invoice.due > 0, Invoice.status.not_in(["CANCELLED", "DRAFT"]))


def call_list(db: Session, tenant_id: str, bucket: Optional[str] = None, query: Optional[str] = None) -> dict:
    """Patients with outstanding dues, oldest first (for follow-up calls). Derived on every call."""
    if bucket and bucket not in BUCKETS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"bucket must be one of {', '.join(BUCKETS)}.")
    stmt = _open_dues(tenant_id)
    if query and query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(Patient.name.ilike(q) | Patient.phone.ilike(q) | Patient.patient_code.ilike(q) | Invoice.invoice_no.ilike(q))
    per: dict = defaultdict(list)
    for inv in db.execute(stmt).scalars().all():
        per[inv.patient_id].append(inv)
    rows = []
    totals = {b: 0 for b in BUCKETS}
    for invs in per.values():
        pat = invs[0].patient
        oldest = max(due_age_days(i) for i in invs)
        for i in invs:
            totals[age_bucket(due_age_days(i))] += i.due
        row = dict(
            patient_id=pat.id, patient_code=pat.patient_code, patient_name=pat.name, patient_phone=pat.phone,
            total_due=sum(i.due for i in invs), invoice_count=len(invs), oldest_age_days=oldest, age_bucket=age_bucket(oldest),
            invoices=[dict(invoice_id=i.id, invoice_no=i.invoice_no, due=i.due, age_days=due_age_days(i), age_bucket=age_bucket(due_age_days(i)))
                      for i in sorted(invs, key=lambda x: x.created_at)],
        )
        if bucket and not any(x["age_bucket"] == bucket for x in row["invoices"]):
            continue
        rows.append(row)
    rows.sort(key=lambda r: (-r["oldest_age_days"], -r["total_due"]))
    return {"bucket_totals": totals, "total_due": sum(totals.values()), "patients": rows}


# ---------------------------------------------------------------- write-off (D11)
def _writeoff_dict(w: DueWriteOff, db: Session) -> dict:
    inv = db.get(Invoice, w.invoice_id)
    pat = db.get(Patient, w.patient_id)
    req = db.get(Staff, w.requested_by_id)
    dec = db.get(Staff, w.decided_by_id) if w.decided_by_id else None
    return dict(
        id=w.id, invoice_id=w.invoice_id, invoice_no=inv.invoice_no if inv else None, patient_name=pat.name if pat else None,
        amount=w.amount, reason=w.reason, status=w.status, admin_limit_at_request=w.admin_limit_at_request,
        requested_by_name=req.display_name if req else None, requested_by_role=w.requested_by_role,
        decided_by_name=dec.display_name if dec else None, decided_at=w.decided_at, decision_note=w.decision_note,
        created_at=w.created_at, invoice_due_now=inv.due if inv else None,
    )


def _apply(db: Session, w: DueWriteOff, inv: Invoice, approver: CurrentActor, how: str) -> None:
    before = f"due Tk {inv.due}, written off so far Tk {inv.written_off}"
    inv.due -= w.amount
    inv.written_off += w.amount
    accounting_service.post_due_written_off(db, w.tenant_id, inv, w, approver.id)  # Prompt 18
    log_audit_event(
        db=db, tenant_id=w.tenant_id, action="DUE_WRITTEN_OFF", entity_type="INVOICE", entity_id=inv.id,
        acting_role=approver.role, actor_id=approver.id, before_value=before,
        after_value=f"Wrote off Tk {w.amount} as bad debt ({how}); due now Tk {inv.due}, written off Tk {inv.written_off}. "
                    f"Not a discount. Reason: {w.reason}",
    )


def _guard(actor: CurrentActor) -> None:
    if actor.role not in WRITEOFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an Admin or the Owner can write off a due.")


def write_off(db: Session, actor: CurrentActor, invoice_id: int, amount: int, reason: str) -> dict:
    _guard(actor)
    text = (reason or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to write off a due.")
    inv = db.execute(select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == actor.tenant_id).with_for_update()).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if inv.status in ("CANCELLED", "DRAFT") or inv.due <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This invoice has no outstanding due to write off.")
    if amount <= 0 or amount > inv.due:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The amount must be between 1 and the current due (Tk {inv.due}).")
    pending = db.execute(select(DueWriteOff.id).where(DueWriteOff.invoice_id == inv.id, DueWriteOff.status == "PENDING_OWNER")).first()
    if pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A write-off request for this invoice is already waiting for the Owner.")
    limit = settings_service.get_int(db, actor.tenant_id, "writeoff_admin_limit")
    direct = actor.role == "OWNER" or (inv.written_off + amount) <= limit
    w = DueWriteOff(tenant_id=actor.tenant_id, invoice_id=inv.id, patient_id=inv.patient_id, amount=amount, reason=text,
                    status="APPLIED" if direct else "PENDING_OWNER", admin_limit_at_request=limit,
                    requested_by_id=actor.id, requested_by_role=actor.role)
    if direct:
        w.decided_by_id, w.decided_at = actor.id, utc_now()
    db.add(w)
    db.flush()
    if direct:
        _apply(db, w, inv, actor, "Owner" if actor.role == "OWNER" else f"within the Admin limit Tk {limit}")
    else:
        log_audit_event(
            db=db, tenant_id=actor.tenant_id, action="DUE_WRITEOFF_REQUESTED", entity_type="INVOICE", entity_id=inv.id,
            acting_role=actor.role, actor_id=actor.id,
            after_value=f"Requested write-off of Tk {amount}: above the Admin limit (Tk {limit}); waiting for the Owner. Reason: {text}")
    db.flush()
    return _writeoff_dict(w, db)


def decide_writeoff(db: Session, actor: CurrentActor, writeoff_id: int, approve: bool, note: Optional[str]) -> dict:
    if actor.role != "OWNER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the Owner can approve or reject a write-off above the Admin limit.")
    w = db.execute(select(DueWriteOff).where(DueWriteOff.id == writeoff_id, DueWriteOff.tenant_id == actor.tenant_id).with_for_update()).scalar_one_or_none()
    if w is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Write-off request not found.")
    if w.status != "PENDING_OWNER":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This request is already {w.status}.")
    inv = db.execute(select(Invoice).where(Invoice.id == w.invoice_id).with_for_update()).scalar_one()
    clean = (note or "").strip() or None
    if approve:
        if w.amount > inv.due:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"The due is now Tk {inv.due}, less than the requested Tk {w.amount}. Reject it and ask for a new request.")
        w.status = "APPLIED"
        _apply(db, w, inv, actor, "approved by the Owner")
    else:
        w.status = "REJECTED"
        log_audit_event(db=db, tenant_id=actor.tenant_id, action="DUE_WRITEOFF_REJECTED", entity_type="INVOICE", entity_id=inv.id,
                        acting_role=actor.role, actor_id=actor.id,
                        after_value=f"Owner rejected the write-off of Tk {w.amount}" + (f": {clean}" if clean else ""))
    w.decided_by_id, w.decided_at, w.decision_note = actor.id, utc_now(), clean
    db.flush()
    return _writeoff_dict(w, db)


def list_writeoffs(db: Session, tenant_id: str, status_filter: Optional[str] = None) -> List[dict]:
    stmt = select(DueWriteOff).where(DueWriteOff.tenant_id == tenant_id).order_by(DueWriteOff.created_at.desc()).limit(200)
    if status_filter:
        stmt = stmt.where(DueWriteOff.status == status_filter.upper())
    return [_writeoff_dict(w, db) for w in db.execute(stmt).scalars().all()]


# ---------------------------------------------------------------- doctor balances (D43)
def doctor_balances(db: Session, tenant_id: str) -> dict:
    """Two separate figures per doctor; never summed together. Source rows: doctor_balance_entries."""
    rows = db.execute(
        select(DoctorBalanceEntry.referrer_id, DoctorBalanceEntry.kind, func.sum(DoctorBalanceEntry.amount), func.max(DoctorBalanceEntry.created_at))
        .where(DoctorBalanceEntry.tenant_id == tenant_id).group_by(DoctorBalanceEntry.referrer_id, DoctorBalanceEntry.kind)
    ).all()
    per: dict = defaultdict(lambda: {"wholesale_receivable": 0, "professional_fee_payable": 0, "last_entry_at": None})
    for rid, kind, total, last in rows:
        key = "wholesale_receivable" if kind == "WHOLESALE_RECEIVABLE" else "professional_fee_payable"
        per[rid][key] = int(total or 0)
        if per[rid]["last_entry_at"] is None or last > per[rid]["last_entry_at"]:
            per[rid]["last_entry_at"] = last
    items = []
    for rid, v in per.items():
        r = db.get(Referrer, rid)
        items.append(dict(referrer_id=rid, name=r.name if r else f"#{rid}", registration_no=r.registration_no if r else None, **v))
    items.sort(key=lambda x: x["name"].lower())
    return {
        "items": items,
        "entry_count": db.execute(select(func.count(DoctorBalanceEntry.id)).where(DoctorBalanceEntry.tenant_id == tenant_id)).scalar_one(),
        "note": ("The wholesale receivable (the doctor owes the center) and the professional-fee payable (the center owes the doctor) "
                 "are kept apart on purpose. Their source rows come from wholesale billing (Module 28) and visit-fee handling "
                 "(Modules 20 / 28), which are not built yet, so these figures stay at 0 until then."),
    }

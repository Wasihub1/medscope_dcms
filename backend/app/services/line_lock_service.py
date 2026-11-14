"""Prompt 12: one place for the invoice-line lock at RESULT COMPLETION and the owner same-day unlock (D14).

Lock events (unchanged for sample tests): Sample Taken / spoiled-rejected lock the line (worklist_service).
New in Prompt 12: a test that needs NO sample (imaging, explicit no-sample marker) locks at the moment its
order becomes COMPLETED (result completion). `IMAGING_PERFORMED` is now only a status label.
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.samples import requires_sample
from backend.app.core.security import CurrentActor
from backend.app.core.timezone import utc_now
from backend.app.models.business_day import BusinessDay
from backend.app.models.invoice import InvoiceLine
from backend.app.services.audit_service import log_audit_event

COMPLETION_LOCK_REASON = "Result completed (line locked)"


def lock_line_at_result_completion(order, when=None) -> bool:
    """Lock the invoice line of a no-sample test when its result is completed. Idempotent.
    Sample-based tests already lock at Sample Taken and are left alone."""
    line = getattr(order, "invoice_line", None)
    if line is None or line.is_locked:
        return False
    if requires_sample(line.test, order):
        return False
    line.is_locked = True
    line.locked_at = when or utc_now()
    line.locked_reason = COMPLETION_LOCK_REASON
    return True


def unlock_line_same_day(db: Session, actor: CurrentActor, line_id: int, reason: Optional[str]) -> InvoiceLine:
    """D14: OWNER only (permission `invoice.line_unlock`), reason required, same business day only.
    One rule for every test type (imaging included). Does not change the order, result or sample."""
    text = (reason or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required to unlock a line.")
    line = db.execute(
        select(InvoiceLine).where(InvoiceLine.id == line_id, InvoiceLine.tenant_id == actor.tenant_id).with_for_update()
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice line not found.")
    if line.status == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This line is cancelled.")
    if not line.is_locked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This line is not locked.")
    day = db.execute(
        select(BusinessDay).where(BusinessDay.tenant_id == actor.tenant_id, BusinessDay.status == "OPEN")
        .order_by(BusinessDay.opened_at.desc())
    ).scalars().first()
    if day is None or line.locked_at is None or line.locked_at < day.opened_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A locked line can only be unlocked on the same business day it was locked.",
        )
    before = f"locked: {line.locked_reason or 'locked'}"
    line.is_locked = False
    line.locked_at = None
    line.locked_reason = None
    db.flush()
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action="INVOICE_LINE_UNLOCKED", entity_type="INVOICE_LINE",
        entity_id=line.id, acting_role=actor.role, actor_id=actor.id,
        before_value=before, after_value=f"Unlocked same business day | reason: {text}",
    )
    return line

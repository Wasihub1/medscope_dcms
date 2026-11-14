from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.timezone import utc_now
from sqlalchemy import func, select
from backend.app.core.soft_delete import audit_text_with_reason
from backend.app.models.audit import AuditLog


def log_audit_event(
    db: Session,
    tenant_id: str,
    action: str,
    entity_type: str,
    entity_id: str | int,
    acting_role: str,
    actor_id: Optional[int] = None,
    before_value: Optional[str] = None,
    after_value: Optional[str] = None,
) -> AuditLog:
    """Appends an immutable audit log row within the current transaction."""
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        acting_role=acting_role,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before_value=before_value,
        after_value=after_value,
        created_at=utc_now(),
    )
    db.add(entry)
    db.flush()
    return entry


REPRINT_ACTIONS = {"INVOICE": "INVOICE_REPRINTED", "REPORT": "REPORT_REPRINTED"}


def count_reprints(db: Session, tenant_id: str, entity_type: str, entity_id: str | int) -> int:
    """Earlier print/reprint events of one invoice or report (read from the one audit log)."""
    return db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == REPRINT_ACTIONS[entity_type],
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == str(entity_id),
        )
    ).scalar_one()


def log_reprint_event(
    db: Session,
    tenant_id: str,
    entity_type: str,
    entity_id: str | int,
    actor_id: int,
    acting_role: str,
    reason: Optional[str] = None,
) -> AuditLog:
    """Prompt 19B: a print/reprint is an ordinary audit row (the separate reprint_logs table was folded in).
    before = number of earlier prints, after = this print's number and the reason."""
    prior = count_reprints(db, tenant_id, entity_type, entity_id)
    return log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=REPRINT_ACTIONS[entity_type],
        entity_type=entity_type,
        entity_id=entity_id,
        acting_role=acting_role,
        actor_id=actor_id,
        before_value=f"{prior} earlier print(s)",
        after_value=audit_text_with_reason(f"Print #{prior + 1}", reason),
    )

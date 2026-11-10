from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.timezone import utc_now
from backend.app.models.audit import AuditLog, ReprintLog


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


def log_reprint_event(
    db: Session,
    tenant_id: str,
    entity_type: str,
    entity_id: str | int,
    reprinted_by_id: int,
    reason: Optional[str] = None,
) -> ReprintLog:
    """Appends an immutable reprint audit log row."""
    entry = ReprintLog(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        reprinted_by_id=reprinted_by_id,
        reason=reason,
        reprinted_at=utc_now(),
    )
    db.add(entry)
    db.flush()
    return entry


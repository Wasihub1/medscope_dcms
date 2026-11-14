"""Module 23 audit viewer (Prompt 11 slice, completed in Prompt 19B). Read-only: paginated list, filter metadata and a
CSV export of the same filters. The only write is the export's own audit row (the viewer audits itself).
No update or delete exists here, and the database refuses them anyway (append-only trigger)."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.audit_domains import domain_condition, domain_labels, domain_of
from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor
from backend.app.core.soft_delete import audit_text_with_reason, extract_reason
from backend.app.models.audit import AuditLog
from backend.app.models.user import Staff
from backend.app.schemas.soft_delete import AuditActor, AuditDomain, AuditLogItem, AuditLogMeta, AuditLogPage
from backend.app.services.accounting_report_service import to_csv
from backend.app.services.audit_service import log_audit_event

router = APIRouter()


def _filters(tenant_id, action, entity_type, actor_id, date_from, date_to, domain=None, acting_role=None, q=None):
    conds = [AuditLog.tenant_id == tenant_id]
    if action and action.strip():
        conds.append(AuditLog.action == action.strip())
    if entity_type and entity_type.strip():
        conds.append(AuditLog.entity_type == entity_type.strip())
    if actor_id is not None:
        conds.append(AuditLog.actor_id == actor_id)
    if acting_role and acting_role.strip():
        conds.append(AuditLog.acting_role == acting_role.strip())
    if domain and domain.strip():
        dc = domain_condition(AuditLog.action, domain.strip())
        if dc is not None:
            conds.append(dc)
    if q and q.strip():
        term = q.strip()
        conds.append(or_(
            AuditLog.action.icontains(term, autoescape=True),
            AuditLog.entity_type.icontains(term, autoescape=True),
            AuditLog.entity_id.icontains(term, autoescape=True),
            AuditLog.before_value.icontains(term, autoescape=True),
            AuditLog.after_value.icontains(term, autoescape=True),
        ))
    if date_from:
        conds.append(AuditLog.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        conds.append(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    return conds


def _query(tenant_id, conds):
    return (select(AuditLog, Staff.display_name)
            .outerjoin(Staff, Staff.id == AuditLog.actor_id)
            .where(*conds)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()))


@router.get("/meta", response_model=AuditLogMeta, summary="Filter lists: actions, entity types, domains, roles, actors")
def audit_meta(actor: CurrentActor = Depends(require_permission("audit.view")), db: Session = Depends(get_db)):
    t = actor.tenant_id
    actions = db.execute(select(AuditLog.action).where(AuditLog.tenant_id == t).distinct().order_by(AuditLog.action)).scalars().all()
    types = db.execute(select(AuditLog.entity_type).where(AuditLog.tenant_id == t).distinct().order_by(AuditLog.entity_type)).scalars().all()
    roles = db.execute(select(AuditLog.acting_role).where(AuditLog.tenant_id == t).distinct().order_by(AuditLog.acting_role)).scalars().all()
    actors = db.execute(
        select(Staff.id, Staff.display_name).where(Staff.id.in_(select(AuditLog.actor_id).where(AuditLog.tenant_id == t, AuditLog.actor_id.is_not(None)).distinct()))
        .order_by(Staff.display_name)
    ).all()
    return AuditLogMeta(
        actions=list(actions), entity_types=list(types), roles=list(roles),
        domains=[AuditDomain(**d) for d in domain_labels()],
        actors=[AuditActor(id=i, name=n) for i, n in actors],
    )


def _item(a: AuditLog, name: Optional[str]) -> AuditLogItem:
    return AuditLogItem(
        id=a.id, created_at=a.created_at, actor_id=a.actor_id, actor_name=name, acting_role=a.acting_role,
        action=a.action, domain=domain_of(a.action), entity_type=a.entity_type, entity_id=a.entity_id,
        reason=extract_reason(a.after_value), before_value=a.before_value, after_value=a.after_value,
    )


@router.get("", response_model=AuditLogPage, summary="Read-only audit log, newest first (audit.view)")
def list_audit_logs(
    action: Optional[str] = Query(default=None, description="Exact action, e.g. TEST_SOFT_DELETED"),
    entity_type: Optional[str] = Query(default=None),
    actor_id: Optional[int] = Query(default=None),
    domain: Optional[str] = Query(default=None, description="Business domain key from /audit-logs/meta, e.g. discounts"),
    acting_role: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="Free text across action, entity type/id and the before/after text"),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None, description="Inclusive"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    actor: CurrentActor = Depends(require_permission("audit.view")),
    db: Session = Depends(get_db),
):
    conds = _filters(actor.tenant_id, action, entity_type, actor_id, date_from, date_to, domain, acting_role, q)
    total = db.execute(select(func.count(AuditLog.id)).where(*conds)).scalar_one()
    rows = db.execute(_query(actor.tenant_id, conds).offset((page - 1) * size).limit(size)).all()
    return AuditLogPage(items=[_item(a, name) for a, name in rows], total=total, page=page, size=size, pages=max(1, -(-total // size)))


CSV_COLUMNS = ["id", "when_utc", "actor", "actor_id", "acting_role", "domain", "action", "entity_type", "entity_id", "reason", "before", "after"]


def _csv_safe(v):
    """Free text that starts with = + - @ would be run as a formula by a spreadsheet; a leading apostrophe stops that."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", chr(9), chr(13)) else v


@router.get("/export", summary="CSV export of the audit log with the same filters as the list (audit.view); the export is itself audited")
def export_audit_logs(
    action: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    actor_id: Optional[int] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    acting_role: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    actor: CurrentActor = Depends(require_permission("audit.view")),
    db: Session = Depends(get_db),
):
    conds = _filters(actor.tenant_id, action, entity_type, actor_id, date_from, date_to, domain, acting_role, q)
    rows = db.execute(_query(actor.tenant_id, conds)).all()
    out = []
    for a, name in rows:
        out.append({k: _csv_safe(v) for k, v in {
            "id": a.id, "when_utc": a.created_at.astimezone(timezone.utc).isoformat(), "actor": name or ("System" if a.actor_id is None else ""),
            "actor_id": a.actor_id if a.actor_id is not None else "", "acting_role": a.acting_role, "domain": domain_of(a.action),
            "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id, "reason": extract_reason(a.after_value) or "",
            "before": a.before_value or "", "after": a.after_value or "",
        }.items()})
    applied = {k: v for k, v in {
        "domain": domain, "action": action, "entity_type": entity_type, "actor_id": actor_id, "acting_role": acting_role,
        "q": q, "date_from": date_from.isoformat() if date_from else None, "date_to": date_to.isoformat() if date_to else None,
    }.items() if v not in (None, "")}
    # The viewer audits itself: who exported, with which filters, how many rows (written after the rows were read).
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action="AUDIT_LOG_EXPORTED", entity_type="AUDIT_LOG", entity_id="export",
        acting_role=actor.role, actor_id=actor.id, before_value=None,
        after_value=audit_text_with_reason(f"Exported {len(out)} row(s) as CSV; filters: {applied or 'none'}", None),
    )
    db.commit()
    return Response(to_csv(out, CSV_COLUMNS), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'})

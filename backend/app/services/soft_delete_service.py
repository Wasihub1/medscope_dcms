"""Prompt 11: soft delete / restore / Deleted view for referrers (doctors + 3rd parties) and
catalog tests. Users have the same rules inside user_admin_service (they also touch rooms/sessions).

New selection is blocked (every normal list filters `deleted_at IS NULL`); nothing that already
references the row is touched, because bills/lines/orders carry their own snapshots and links.
Audit rows are written in the same transaction as the change.
"""
from typing import Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.core.security import CurrentActor
from backend.app.core.soft_delete import audit_text_with_reason, clean_reason
from backend.app.core.timezone import utc_now
from backend.app.models.referrer import Referrer
from backend.app.models.test import Test
from backend.app.models.user import Staff
from backend.app.schemas.soft_delete import DeletedItemResponse
from backend.app.services.audit_service import log_audit_event


def staff_names(db: Session, ids) -> Dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.execute(select(Staff.id, Staff.display_name).where(Staff.id.in_(ids))).all()
    return {i: n for i, n in rows}


def _get(db: Session, model, tenant_id: str, row_id: int, label: str):
    row = db.get(model, row_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found.")
    return row


def _soft_delete(db: Session, actor: CurrentActor, row, entity_type: str, action: str, label: str, reason: Optional[str]):
    text = clean_reason(reason)
    if row.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{label} is already deleted.")
    row.deleted_at = utc_now()
    row.deleted_by_id = actor.id
    row.delete_reason = text
    db.flush()
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action=action, entity_type=entity_type, entity_id=row.id,
        acting_role=actor.role, actor_id=actor.id,
        before_value=f"{label} visible in new selection",
        after_value=audit_text_with_reason(f"Soft-deleted {label}", text),
    )
    return row


def _restore(db: Session, actor: CurrentActor, row, entity_type: str, action: str, label: str):
    if row.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{label} is not deleted.")
    before = audit_text_with_reason(
        f"Deleted at {row.deleted_at.isoformat()} by staff {row.deleted_by_id}", row.delete_reason
    )
    row.deleted_at = None
    row.deleted_by_id = None
    row.delete_reason = None
    db.flush()
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action=action, entity_type=entity_type, entity_id=row.id,
        acting_role=actor.role, actor_id=actor.id, before_value=before, after_value=f"Restored {label}",
    )
    return row


# --------------------------------------------------------------------------- referrers
def _ref_label(r: Referrer) -> str:
    return f"{r.referrer_type} '{r.name}'"


def delete_referrer(db: Session, actor: CurrentActor, referrer_id: int, reason: Optional[str]) -> Referrer:
    r = _get(db, Referrer, actor.tenant_id, referrer_id, "Doctor / referrer")
    return _soft_delete(db, actor, r, "REFERRER", "REFERRER_SOFT_DELETED", _ref_label(r), reason)


def restore_referrer(db: Session, actor: CurrentActor, referrer_id: int) -> Referrer:
    r = _get(db, Referrer, actor.tenant_id, referrer_id, "Doctor / referrer")
    return _restore(db, actor, r, "REFERRER", "REFERRER_RESTORED", _ref_label(r))


def list_deleted_referrers(db: Session, tenant_id: str, q: Optional[str] = None, type_: Optional[str] = None) -> List[DeletedItemResponse]:
    stmt = select(Referrer).where(Referrer.tenant_id == tenant_id, Referrer.deleted_at.is_not(None))
    if type_ and type_.strip():
        stmt = stmt.where(Referrer.referrer_type.ilike(f"%{type_.strip()}%"))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Referrer.name.ilike(like), Referrer.phone.ilike(like), Referrer.specialty.ilike(like)))
    rows = list(db.execute(stmt.order_by(Referrer.deleted_at.desc())).scalars().all())
    names = staff_names(db, [r.deleted_by_id for r in rows])
    return [
        DeletedItemResponse(
            id=r.id, kind="REFERRER", title=r.name,
            subtitle=" · ".join(x for x in (r.referrer_type, r.specialty, r.phone) if x),
            deleted_at=r.deleted_at, deleted_by_id=r.deleted_by_id,
            deleted_by_name=names.get(r.deleted_by_id), delete_reason=r.delete_reason,
        )
        for r in rows
    ]


# --------------------------------------------------------------------------- tests
def _test_label(t: Test) -> str:
    return f"test '{t.code} {t.name}'"


def delete_test(db: Session, actor: CurrentActor, test_id: int, reason: Optional[str]) -> Test:
    t = _get(db, Test, actor.tenant_id, test_id, "Test")
    return _soft_delete(db, actor, t, "TEST", "TEST_SOFT_DELETED", _test_label(t), reason)


def restore_test(db: Session, actor: CurrentActor, test_id: int) -> Test:
    t = _get(db, Test, actor.tenant_id, test_id, "Test")
    return _restore(db, actor, t, "TEST", "TEST_RESTORED", _test_label(t))


def list_deleted_tests(db: Session, tenant_id: str, q: Optional[str] = None) -> List[DeletedItemResponse]:
    stmt = select(Test).where(Test.tenant_id == tenant_id, Test.deleted_at.is_not(None))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Test.code.ilike(like), Test.name.ilike(like), Test.department.ilike(like)))
    rows = list(db.execute(stmt.order_by(Test.deleted_at.desc())).scalars().all())
    names = staff_names(db, [t.deleted_by_id for t in rows])
    return [
        DeletedItemResponse(
            id=t.id, kind="TEST", title=f"[{t.code}] {t.name}", subtitle=t.department,
            deleted_at=t.deleted_at, deleted_by_id=t.deleted_by_id,
            deleted_by_name=names.get(t.deleted_by_id), delete_reason=t.delete_reason,
        )
        for t in rows
    ]

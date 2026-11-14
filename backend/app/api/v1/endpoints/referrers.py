from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.models.referrer import Referrer
from backend.app.schemas.referrer import ReferrerCreate, ReferrerResponse, ReferrerUpdate
from backend.app.schemas.soft_delete import DeleteRequest, DeletedItemResponse, RestoredResponse
from backend.app.services import soft_delete_service as sd
from backend.app.services.audit_service import log_audit_event

router = APIRouter()


@router.get("", response_model=List[ReferrerResponse], summary="Search and list active referrers")
def list_referrers(
    q: Optional[str] = Query(default="", description="Search by name, phone, specialty"),
    type: Optional[str] = Query(default=None, description="Doctor, Third Party, etc."),
    limit: int = Query(default=100, le=500),
    actor: CurrentActor = Depends(require_permission("referrer.view")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Referrer)
        .where(Referrer.tenant_id == actor.tenant_id, Referrer.active == True, Referrer.deleted_at.is_(None))
        .order_by(Referrer.name)
    )
    if type and type.strip():
        stmt = stmt.where(Referrer.referrer_type.ilike(f"%{type.strip()}%"))
    if q and q.strip():
        clean_q = q.strip()
        stmt = stmt.where(
            or_(
                Referrer.name.ilike(f"%{clean_q}%"),
                Referrer.phone.ilike(f"%{clean_q}%"),
                Referrer.specialty.ilike(f"%{clean_q}%"),
            )
        )
    referrers = list(db.execute(stmt.limit(limit)).scalars().all())
    return [ReferrerResponse.model_validate(r) for r in referrers]


@router.get("/deleted", response_model=List[DeletedItemResponse], summary="Deleted doctors and 3rd parties (Prompt 11, Admin/Owner)")
def list_deleted(
    q: Optional[str] = Query(default=""),
    type: Optional[str] = Query(default=None),
    actor: CurrentActor = Depends(require_permission("referrer.manage")),
    db: Session = Depends(get_db),
):
    return sd.list_deleted_referrers(db, actor.tenant_id, q, type)


@router.patch("/{referrer_id}", response_model=ReferrerResponse, summary="Edit a doctor / 3rd party's own details (Admin/Owner, same key as delete)")
def update_referrer(
    referrer_id: int,
    data: ReferrerUpdate,
    actor: CurrentActor = Depends(require_permission("referrer.manage")),
    db: Session = Depends(get_db),
):
    """Updates the existing row in place (never delete + recreate), so bills keep their link. Saved bills, doctor
    approvals and reports keep what they already captured; commission is not touched."""
    r = db.execute(select(Referrer).where(Referrer.id == referrer_id, Referrer.tenant_id == actor.tenant_id)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor / referrer not found.")
    if r.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This doctor / 3rd party is deleted. Restore it before editing.")
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None or "referrer_type" in changes and changes["referrer_type"] is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and type cannot be empty.")
    before, after = [], []
    for field, value in changes.items():
        new = value.strip() if isinstance(value, str) else value
        if field in ("name", "referrer_type") and not new:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name and type cannot be empty.")
        new = new or None if field not in ("name", "referrer_type") else new
        old = getattr(r, field)
        if old != new:
            before.append(f"{field}={old!r}")
            after.append(f"{field}={new!r}")
            setattr(r, field, new)
    if after:
        log_audit_event(db=db, tenant_id=actor.tenant_id, action="UPDATE_REFERRER", entity_type="REFERRER", entity_id=r.id,
                        acting_role=actor.role, actor_id=actor.id, before_value="; ".join(before), after_value="; ".join(after))
    db.commit()
    db.refresh(r)
    return ReferrerResponse.model_validate(r)


@router.post("/{referrer_id}/delete", response_model=DeletedItemResponse, summary="Soft-delete a doctor / 3rd party (reason required)")
def soft_delete(
    referrer_id: int,
    data: DeleteRequest = Body(default_factory=DeleteRequest),
    actor: CurrentActor = Depends(require_permission("referrer.manage")),
    db: Session = Depends(get_db),
):
    r = sd.delete_referrer(db, actor, referrer_id, data.reason)
    db.commit()
    return DeletedItemResponse(
        id=r.id, kind="REFERRER", title=r.name, subtitle=r.referrer_type,
        deleted_at=r.deleted_at, deleted_by_id=r.deleted_by_id,
        deleted_by_name=sd.staff_names(db, [r.deleted_by_id]).get(r.deleted_by_id), delete_reason=r.delete_reason,
    )


@router.post("/{referrer_id}/restore", response_model=RestoredResponse, summary="Restore a deleted doctor / 3rd party")
def restore(
    referrer_id: int,
    actor: CurrentActor = Depends(require_permission("referrer.manage")),
    db: Session = Depends(get_db),
):
    r = sd.restore_referrer(db, actor, referrer_id)
    db.commit()
    return RestoredResponse(id=r.id, kind="REFERRER", title=r.name, message="Doctor / referrer restored.")


@router.post("", response_model=ReferrerResponse, status_code=status.HTTP_201_CREATED, summary="Create a basic referrer inside invoice workflow")
def create_basic_referrer(
    data: ReferrerCreate,
    actor: CurrentActor = Depends(require_permission("referrer.create")),
    db: Session = Depends(get_db),
):
    referrer = Referrer(
        tenant_id=actor.tenant_id,
        name=data.name.strip(),
        referrer_type=data.referrer_type.strip(),
        phone=data.phone.strip() if data.phone else None,
        registration_no=data.registration_no.strip() if data.registration_no else None,
        specialty=data.specialty.strip() if data.specialty else None,
        chamber_address=data.chamber_address.strip() if data.chamber_address else None,
        active=True,
        commission_type=data.commission_type or "PERCENTAGE",
        commission_rate=data.commission_rate or 0,
    )
    db.add(referrer)
    db.commit()
    db.refresh(referrer)

    log_audit_event(
        db=db,
        tenant_id=actor.tenant_id,
        action="CREATE_REFERRER",
        entity_type="REFERRER",
        entity_id=referrer.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"Created {referrer.referrer_type}: {referrer.name} (Commission: {'configured' if referrer.commission_rate > 0 else 'none'})",
    )
    return ReferrerResponse.model_validate(referrer)

    log_audit_event(
        db=db,
        tenant_id=actor.tenant_id,
        action="CREATE_BASIC_REFERRER",
        entity_type="REFERRER",
        entity_id=referrer.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"Name: {referrer.name}, Type: {referrer.referrer_type}, Phone: {referrer.phone}",
    )
    return ReferrerResponse.model_validate(referrer)


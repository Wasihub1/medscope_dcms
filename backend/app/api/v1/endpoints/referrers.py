from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, or_, desc
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.models.referrer import Referrer
from backend.app.schemas.referrer import ReferrerCreate, ReferrerResponse
from backend.app.services.audit_service import log_audit_event

router = APIRouter()


@router.get("", response_model=List[ReferrerResponse], summary="Search and list active referrers")
def list_referrers(
    q: Optional[str] = Query(default="", description="Search by name, phone, specialty"),
    type: Optional[str] = Query(default=None, description="Doctor, Third Party, etc."),
    limit: int = Query(default=100, le=500),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Referrer)
        .where(Referrer.tenant_id == actor.tenant_id, Referrer.active == True)
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


@router.post("", response_model=ReferrerResponse, status_code=status.HTTP_201_CREATED, summary="Create a basic referrer inside invoice workflow")
def create_basic_referrer(
    data: ReferrerCreate,
    actor: CurrentActor = Depends(require_receptionist),
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


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.models.user import Staff
from backend.app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from backend.app.services.audit_service import log_audit_event

router = APIRouter()


@router.get("/me", response_model=ProfileResponse, summary="Get own profile (any role with profile.manage)")
@router.get("", response_model=ProfileResponse, summary="Get own profile (alias for /me)")
def get_my_profile(
    actor: CurrentActor = Depends(require_permission("profile.manage")),
    db: Session = Depends(get_db),
):
    staff = db.get(Staff, actor.id)
    if not staff:
        return ProfileResponse(
            id=actor.id,
            username=actor.username,
            display_name=actor.display_name,
            role=actor.role,
            email=actor.email,
            phone=actor.phone,
            address="Front Desk, Seba Diagnostic Center",
            avatar_url=None,
            tenant_id=actor.tenant_id,
            tenant_name="Seba Diagnostic Center",
        )
    return ProfileResponse(
        id=staff.id,
        username=staff.username,
        display_name=staff.display_name,
        role=staff.role,
        email=staff.email,
        phone=staff.phone,
        address=staff.address,
        avatar_url=staff.avatar_url,
        tenant_id=staff.tenant_id,
        tenant_name=staff.tenant.name if staff.tenant else "Seba Diagnostic Center",
    )


@router.put("/me", response_model=ProfileResponse, summary="Update permitted personal profile fields")
@router.put("", response_model=ProfileResponse, summary="Update profile (alias)")
@router.patch("/me", response_model=ProfileResponse, summary="Patch profile")
@router.patch("", response_model=ProfileResponse, summary="Patch profile (alias)")
def update_my_profile(
    data: ProfileUpdateRequest,
    actor: CurrentActor = Depends(require_permission("profile.manage")),
    db: Session = Depends(get_db),
):
    staff = db.get(Staff, actor.id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff record not found.")

    before_val = f"Name: {staff.display_name}, Phone: {staff.phone}, Email: {staff.email}"

    staff.display_name = data.display_name.strip()
    staff.phone = data.phone.strip() if data.phone else None
    staff.email = data.email.strip() if data.email else None
    staff.address = data.address.strip() if data.address else None
    staff.avatar_url = data.avatar_url.strip() if data.avatar_url else None

    log_audit_event(
        db=db,
        tenant_id=actor.tenant_id,
        action="UPDATE_OWN_PROFILE",
        entity_type="STAFF",
        entity_id=staff.id,
        acting_role=actor.role,
        actor_id=staff.id,
        before_value=before_val,
        after_value=f"Name: {staff.display_name}, Phone: {staff.phone}, Email: {staff.email}",
    )
    # Prompt 10E: commit after the audit row (it was written after the commit and never saved)
    db.commit()
    db.refresh(staff)

    return ProfileResponse(
        id=staff.id,
        username=staff.username,
        display_name=staff.display_name,
        role=staff.role,
        email=staff.email,
        phone=staff.phone,
        address=staff.address,
        avatar_url=staff.avatar_url,
        tenant_id=staff.tenant_id,
        tenant_name=staff.tenant.name if staff.tenant else "Seba Diagnostic Center",
    )


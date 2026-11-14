"""Prompt 10D Part 5: user management endpoints (Owner/Admin 'Create User' tab).
All routes require the 'user.manage' permission. No delete endpoint (Prompt 11 handles that)."""
from typing import List

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor
from backend.app.schemas.auth import AuthMessageResponse
from backend.app.schemas.soft_delete import DeleteRequest, DeletedItemResponse
from backend.app.schemas.user_admin import (
    UserAdminMetaResponse,
    UserCreateRequest,
    UserDetailResponse,
    UserPasswordResetRequest,
    UserPermissionOverridesRequest,
    UserRoleRequest,
    UserSummaryResponse,
    UserUpdateRequest,
)
from backend.app.services import user_admin_service as svc

router = APIRouter()
_manage = require_permission("user.manage")


@router.get("/meta", response_model=UserAdminMetaResponse, summary="Roles, permission keys, role defaults and lab sections")
def get_meta(actor: CurrentActor = Depends(_manage)):
    return svc.get_meta()


@router.get("", response_model=List[UserSummaryResponse], summary="List users")
def list_users(actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    return svc.list_users(db, actor.tenant_id)


@router.get("/deleted", response_model=List[DeletedItemResponse], summary="Deleted users (Prompt 11, Admin/Owner)")
def list_deleted(actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    return svc.list_deleted_users(db, actor.tenant_id)


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create a user with one role")
def create_user(data: UserCreateRequest, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.create_user(db, actor, data)
    db.commit()
    return svc.get_user_detail(db, staff)


@router.get("/{user_id}", response_model=UserDetailResponse, summary="User detail with role defaults, overrides and effective permissions")
def get_user(user_id: int, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    return svc.get_user_detail(db, svc.get_user(db, actor.tenant_id, user_id))


@router.patch("/{user_id}", response_model=UserDetailResponse, summary="Update user details")
def update_user(user_id: int, data: UserUpdateRequest, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.update_user(db, actor, svc.get_user(db, actor.tenant_id, user_id), data)
    db.commit()
    return svc.get_user_detail(db, staff)


@router.put("/{user_id}/role", response_model=UserDetailResponse, summary="Set the user's single role")
def set_role(user_id: int, data: UserRoleRequest, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.set_user_role(db, actor, svc.get_user(db, actor.tenant_id, user_id), data.role, data.lab_section)
    db.commit()
    return svc.get_user_detail(db, staff)


@router.post("/{user_id}/deactivate", response_model=UserDetailResponse, summary="Deactivate a user (no delete)")
def deactivate(user_id: int, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.set_user_active(db, actor, svc.get_user(db, actor.tenant_id, user_id), False)
    db.commit()
    return svc.get_user_detail(db, staff)


@router.post("/{user_id}/reactivate", response_model=UserDetailResponse, summary="Reactivate a user")
def reactivate(user_id: int, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.set_user_active(db, actor, svc.get_user(db, actor.tenant_id, user_id), True)
    db.commit()
    return svc.get_user_detail(db, staff)


@router.post("/{user_id}/delete", response_model=UserDetailResponse, summary="Soft-delete a user (reason required; separate from deactivate)")
def soft_delete_user(user_id: int, data: DeleteRequest = Body(default_factory=DeleteRequest), actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.delete_user(db, actor, svc.get_user(db, actor.tenant_id, user_id), data.reason)
    db.commit()
    return svc.get_user_detail(db, staff)


@router.post("/{user_id}/restore", response_model=UserDetailResponse, summary="Restore a deleted user (stays inactive until reactivated)")
def restore_deleted_user(user_id: int, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.restore_user(db, actor, svc.get_user(db, actor.tenant_id, user_id))
    db.commit()
    return svc.get_user_detail(db, staff)


@router.post("/{user_id}/reset-password", response_model=AuthMessageResponse, summary="Reset a user's password")
def reset_password(user_id: int, data: UserPasswordResetRequest, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.get_user(db, actor.tenant_id, user_id)
    svc.reset_user_password(db, actor, staff, data.new_password)
    db.commit()
    return AuthMessageResponse(message=f"Password for '{staff.username}' was reset.")


@router.get("/{user_id}/permissions", response_model=UserDetailResponse, summary="Get per-user permission overrides")
def get_permissions(user_id: int, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    return svc.get_user_detail(db, svc.get_user(db, actor.tenant_id, user_id))


@router.put("/{user_id}/permissions", response_model=UserDetailResponse, summary="Set per-user permission overrides")
def set_permissions(user_id: int, data: UserPermissionOverridesRequest, actor: CurrentActor = Depends(_manage), db: Session = Depends(get_db)):
    staff = svc.set_user_permissions(db, actor, svc.get_user(db, actor.tenant_id, user_id), data.overrides)
    db.commit()
    return svc.get_user_detail(db, staff)

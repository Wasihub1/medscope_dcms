from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import (
    CurrentActor,
    get_current_actor,
    extract_session_token,
)
from backend.app.core.permissions import require_permission
from backend.app.models.user import Staff
from backend.app.schemas.auth import (
    LoginRequest,
    AuthUserResponse,
    ChangePasswordRequest,
    AdminResetPasswordRequest,
    AuthMessageResponse,
)
from backend.app.services import auth_service

router = APIRouter()


def _auth_user_response(db: Session, staff: Staff) -> AuthUserResponse:
    """Prompt 10D: one fixed role per login; every login lands on /dashboard."""
    perms = sorted(auth_service.load_effective_permissions(db, staff))
    return AuthUserResponse(
        id=staff.id,
        tenant_id=staff.tenant_id,
        username=staff.username,
        display_name=staff.display_name,
        roles=[staff.role],
        acting_role=staff.role,
        role=staff.role,
        department=staff.department,
        lab_section=staff.lab_section,
        email=staff.email,
        phone=staff.phone,
        home_route=auth_service.get_home_route_for_role(staff.role),
        permissions=perms,
    )


@router.post("/login", response_model=AuthUserResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates staff with username and password, establishes a server-side session,
    sets an HttpOnly cookie, and returns the acting role profile.
    """
    client_ip = request.client.host if request.client else None
    staff = auth_service.authenticate_user(
        db=db,
        username=req.username,
        password=req.password,
        client_ip=client_ip,
    )

    user_agent = request.headers.get("User-Agent")
    session, raw_token = auth_service.create_session(
        db=db,
        staff=staff,
        requested_role=req.role,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    # Set HttpOnly, SameSite=Lax cookie
    max_age_seconds = settings.SESSION_ABSOLUTE_LIFETIME_HOURS * 3600
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=max_age_seconds,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )

    return _auth_user_response(db, staff)


@router.post("/logout", response_model=AuthMessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(get_current_actor),
):
    """
    Terminates active session and clears the HttpOnly session cookie.
    """
    token = extract_session_token(request)
    if token:
        try:
            session, staff = auth_service.resolve_session(db, token)
            auth_service.revoke_session(db, session, staff)
        except Exception:
            pass  # Session might already be invalidated

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return AuthMessageResponse(message="Successfully logged out")


@router.get("/me", response_model=AuthUserResponse)
def get_me(
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(get_current_actor),
):
    """
    Returns the currently authenticated staff profile, single role, permissions and home route.
    """
    staff = db.get(Staff, actor.id)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found",
        )

    return _auth_user_response(db, staff)


@router.post("/change-password", response_model=AuthMessageResponse)
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(get_current_actor),
):
    """
    Changes password for the authenticated user and terminates other sessions.
    """
    staff = db.get(Staff, actor.id)
    if not staff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")

    auth_service.change_user_password(
        db=db,
        staff=staff,
        old_password=req.old_password,
        new_password=req.new_password,
        acting_role=actor.role,
    )

    # Establish new session after password change
    user_agent = request.headers.get("User-Agent")
    client_ip = request.client.host if request.client else None
    session, raw_token = auth_service.create_session(
        db=db,
        staff=staff,
        requested_role=actor.role,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_ABSOLUTE_LIFETIME_HOURS * 3600,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )
    return AuthMessageResponse(message="Password changed successfully")


# ---------------------------------------------------------------------------
# Admin & Owner User Management Endpoints
# ---------------------------------------------------------------------------
@router.post("/users/{user_id}/reset-password", response_model=AuthMessageResponse)
def admin_reset_password(
    user_id: int,
    req: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: CurrentActor = Depends(require_permission("user.manage")),
):
    """
    Admin or Owner resets another staff member's password and revokes their active sessions.
    """
    target = db.get(Staff, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    admin_staff = db.get(Staff, admin.id)
    auth_service.admin_reset_password(
        db=db,
        admin_actor=admin_staff,
        target_staff=target,
        new_password=req.new_password,
        admin_role=admin.role,
    )
    return AuthMessageResponse(message=f"Password for user '{target.username}' reset successfully.")


@router.post("/users/{user_id}/unlock", response_model=AuthMessageResponse)
def admin_unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: CurrentActor = Depends(require_permission("user.manage")),
):
    """
    Admin or Owner unlocks a locked staff account.
    """
    target = db.get(Staff, user_id)
    if not target or target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    admin_staff = db.get(Staff, admin.id)
    auth_service.admin_unlock_user(
        db=db,
        admin_actor=admin_staff,
        target_staff=target,
        admin_role=admin.role,
    )
    return AuthMessageResponse(message=f"Account for user '{target.username}' unlocked successfully.")

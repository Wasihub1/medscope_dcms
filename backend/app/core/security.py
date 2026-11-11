from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db


class CurrentActor(BaseModel):
    id: int
    tenant_id: str
    username: str
    display_name: str
    role: str  # Acting role in the current session
    email: Optional[str] = None
    phone: Optional[str] = None


def extract_session_token(request: Request) -> Optional[str]:
    """Extracts raw session token from Authorization header, X-Session-Token, or cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    session_header = request.headers.get("X-Session-Token")
    if session_header:
        return session_header.strip()

    cookie_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token.strip()

    return None


def get_current_actor(
    request: Request,
    db: Session = Depends(get_db),
) -> CurrentActor:
    """
    Dependency resolving the authenticated actor from server-side session.
    Rejects missing or invalid sessions with HTTP 401 Unauthorized.
    Enforces CSRF header on state-changing requests when cookie authentication is used.
    """
    token = extract_session_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )

    # CSRF defense: If session was supplied via cookie and method is state-changing, require custom header
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        is_cookie_auth = bool(request.cookies.get(settings.SESSION_COOKIE_NAME))
        if is_cookie_auth:
            csrf_header = request.headers.get("X-Requested-With")
            auth_header = request.headers.get("Authorization")
            if not csrf_header and not auth_header:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF protection error: missing X-Requested-With header",
                )

    from backend.app.services.auth_service import resolve_session
    session, staff = resolve_session(db, token)

    return CurrentActor(
        id=staff.id,
        tenant_id=staff.tenant_id,
        username=staff.username,
        display_name=staff.display_name,
        role=session.acting_role,
        email=staff.email,
        phone=staff.phone,
    )


def require_receptionist(
    actor: CurrentActor = Depends(get_current_actor),
) -> CurrentActor:
    """Ensures actor is permitted to perform Receptionist operations."""
    if actor.role not in ("RECEPTIONIST", "CASHIER", "ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to Receptionist, Cashier, Admin, or Owner roles.",
        )
    return actor


def require_lab_tech_or_admin(
    actor: CurrentActor = Depends(get_current_actor),
) -> CurrentActor:
    """Ensures actor is permitted to perform Laboratory Technician operations."""
    if actor.role not in ("LAB_TECH", "ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to Laboratory Technicians, Admin, or Owner.",
        )
    return actor


def require_admin(
    actor: CurrentActor = Depends(get_current_actor),
) -> CurrentActor:
    """Ensures actor has Admin or Owner authority (e.g. for approving refunds)."""
    if actor.role not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires Admin or Owner authorization.",
        )
    return actor

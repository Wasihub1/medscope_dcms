import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from uuid import uuid4
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import HTTPException, status
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.timezone import utc_now
from backend.app.models.user import Staff, StaffRole, AuthSession, StaffPermissionOverride
from backend.app.core.permissions import effective_permissions
from backend.app.services.audit_service import log_audit_event

# Argon2id password hasher instance
_ph = PasswordHasher()

# Basic in-memory IP/username rate limiter for brute-force protection
_FAILED_ATTEMPTS_LOG: Dict[str, List[datetime]] = defaultdict(list)
_THROTTLE_LIMIT = 20  # max failed attempts within window per key
_THROTTLE_WINDOW_SECONDS = 900  # 15 minutes


def _check_rate_limit(key: str) -> None:
    now = utc_now()
    window_start = now - timedelta(seconds=_THROTTLE_WINDOW_SECONDS)
    # Filter out timestamps older than window
    _FAILED_ATTEMPTS_LOG[key] = [t for t in _FAILED_ATTEMPTS_LOG[key] if t > window_start]
    if len(_FAILED_ATTEMPTS_LOG[key]) >= _THROTTLE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 15 minutes and try again.",
        )


def _record_failed_attempt(key: str) -> None:
    _FAILED_ATTEMPTS_LOG[key].append(utc_now())


def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a plain password against an Argon2id hash."""
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str, username: str) -> None:
    """Ensures password meets minimum length and does not equal username."""
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if password.strip().lower() == username.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must not be identical to username.",
        )


def get_home_route_for_role(role: str) -> str:
    """Prompt 10D (ADL-033): every login lands on the Dashboard, whatever the role."""
    return "/dashboard"


def get_staff_roles(db: Session, staff_id: int, fallback_role: str) -> List[str]:
    """Prompt 10D (ADL-032): one login = one fixed role. Returns a single-item list."""
    role = db.execute(select(StaffRole.role).where(StaffRole.staff_id == staff_id)).scalars().first()
    return [role or fallback_role]


def load_effective_permissions(db: Session, staff: Staff):
    """Role defaults then per-user overrides (backend/app/core/permissions.py)."""
    rows = db.execute(
        select(StaffPermissionOverride.permission_key, StaffPermissionOverride.granted).where(
            StaffPermissionOverride.staff_id == staff.id
        )
    ).all()
    return effective_permissions(staff.role, {k: g for k, g in rows})


def authenticate_user(
    db: Session,
    username: str,
    password: str,
    client_ip: Optional[str] = None,
) -> Staff:
    """
    Authenticates staff credentials with case-insensitive username lookup,
    account lockout protection after 5 failed attempts, and generic error messaging.
    """
    clean_username = username.strip()
    rate_key = f"{client_ip}:{clean_username.lower()}" if client_ip else clean_username.lower()
    _check_rate_limit(rate_key)

    # Case-insensitive query
    staff = db.execute(
        select(Staff).where(func.lower(Staff.username) == clean_username.lower())
    ).scalar_one_or_none()

    # Generic error for nonexistent or inactive user
    if not staff or not staff.active or staff.deleted_at is not None:
        _record_failed_attempt(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Check lockout
    if staff.locked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked due to too many failed login attempts. Please contact an Administrator or Owner.",
        )

    # Verify password
    if not staff.password_hash or not verify_password(password, staff.password_hash):
        _record_failed_attempt(rate_key)
        staff.failed_attempts += 1
        if staff.failed_attempts >= settings.AUTH_MAX_FAILED_ATTEMPTS:
            staff.locked_at = utc_now()
            log_audit_event(
                db=db,
                tenant_id=staff.tenant_id,
                action="AUTH_ACCOUNT_LOCKED",
                entity_type="STAFF",
                entity_id=staff.id,
                acting_role="SYSTEM",
                actor_id=staff.id,
                after_value=f"Account locked at {staff.failed_attempts} failed attempts",
            )
        log_audit_event(
            db=db,
            tenant_id=staff.tenant_id,
            action="AUTH_LOGIN_FAILED",
            entity_type="STAFF",
            entity_id=staff.id,
            acting_role="ANONYMOUS",
            actor_id=staff.id,
            after_value=f"failed_attempts={staff.failed_attempts}",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Authentication succeeded: reset failed attempts
    staff.failed_attempts = 0
    staff.last_login_at = utc_now()
    db.flush()
    return staff


def create_session(
    db: Session,
    staff: Staff,
    requested_role: Optional[str] = None,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Tuple[AuthSession, str]:
    """
    Creates an active server-side session and returns (session_record, raw_session_token).
    """
    # Prompt 10D: one login = one fixed role. The session always carries the user's role.
    acting_role = staff.role
    if requested_role and requested_role.strip().upper() != acting_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not hold the requested role '{requested_role}'.",
        )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session_id = uuid4().hex
    now = utc_now()
    expires_at = now + timedelta(hours=settings.SESSION_ABSOLUTE_LIFETIME_HOURS)

    session = AuthSession(
        id=session_id,
        session_token_hash=token_hash,
        staff_id=staff.id,
        tenant_id=staff.tenant_id,
        acting_role=acting_role,
        created_at=now,
        expires_at=expires_at,
        last_seen_at=now,
        revoked_at=None,
        user_agent=user_agent[:500] if user_agent else None,
        ip_address=ip_address[:50] if ip_address else None,
    )
    db.add(session)

    log_audit_event(
        db=db,
        tenant_id=staff.tenant_id,
        action="AUTH_LOGIN_SUCCESS",
        entity_type="STAFF",
        entity_id=staff.id,
        acting_role=acting_role,
        actor_id=staff.id,
        after_value=f"Session created with acting_role={acting_role}",
    )
    db.commit()
    db.refresh(session)
    return session, raw_token


def resolve_session(db: Session, raw_token: str) -> Tuple[AuthSession, Staff]:
    """
    Resolves raw session token into active (AuthSession, Staff).
    Checks expiration, idle timeout, revoked status, and account lock.
    """
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session token missing",
        )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session = db.execute(
        select(AuthSession).where(AuthSession.session_token_hash == token_hash)
    ).scalar_one_or_none()

    if not session or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or has been revoked",
        )

    now = utc_now()
    # Check absolute lifetime
    if session.expires_at < now:
        session.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
        )

    # Check idle timeout
    idle_limit = timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES)
    if (now - session.last_seen_at) > idle_limit:
        session.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session timed out due to inactivity. Please log in again.",
        )

    staff = db.get(Staff, session.staff_id)
    if not staff or not staff.active or staff.deleted_at is not None:
        session.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff account is disabled",
        )

    if staff.locked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked due to too many failed login attempts.",
        )

    # Update last_seen_at
    session.last_seen_at = now
    db.flush()
    return session, staff


def revoke_session(db: Session, session: AuthSession, staff: Staff) -> None:
    """Revokes a specific session (logout)."""
    session.revoked_at = utc_now()
    log_audit_event(
        db=db,
        tenant_id=staff.tenant_id,
        action="AUTH_LOGOUT",
        entity_type="STAFF",
        entity_id=staff.id,
        acting_role=session.acting_role,
        actor_id=staff.id,
        after_value=f"Session {session.id} revoked",
    )
    db.commit()


def revoke_all_user_sessions(db: Session, staff_id: int, commit: bool = True) -> None:
    """Revokes all active sessions for a staff member (used on password change/reset).
    Prompt 10F: callers that write the user change, its audit row and dependent rows (user
    management) pass commit=False so everything commits once, in one transaction."""
    db.execute(
        update(AuthSession)
        .where(AuthSession.staff_id == staff_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    if commit:
        db.commit()


def change_user_password(
    db: Session,
    staff: Staff,
    old_password: str,
    new_password: str,
    acting_role: str,
) -> None:
    """Changes password for authenticated user and revokes other sessions."""
    if not verify_password(old_password, staff.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    validate_password_strength(new_password, staff.username)

    staff.password_hash = hash_password(new_password)
    staff.password_changed_at = utc_now()
    # Revoke all sessions for security
    revoke_all_user_sessions(db, staff.id)

    log_audit_event(
        db=db,
        tenant_id=staff.tenant_id,
        action="AUTH_PASSWORD_CHANGED",
        entity_type="STAFF",
        entity_id=staff.id,
        acting_role=acting_role,
        actor_id=staff.id,
        after_value="Password changed by user",
    )
    db.commit()


def admin_reset_password(
    db: Session,
    admin_actor: Staff,
    target_staff: Staff,
    new_password: str,
    admin_role: str,
) -> None:
    """Admin/Owner resets another user's password."""
    validate_password_strength(new_password, target_staff.username)
    target_staff.password_hash = hash_password(new_password)
    target_staff.password_changed_at = utc_now()
    target_staff.failed_attempts = 0
    target_staff.locked_at = None
    revoke_all_user_sessions(db, target_staff.id)

    log_audit_event(
        db=db,
        tenant_id=admin_actor.tenant_id,
        action="AUTH_PASSWORD_RESET_BY_ADMIN",
        entity_type="STAFF",
        entity_id=target_staff.id,
        acting_role=admin_role,
        actor_id=admin_actor.id,
        after_value=f"Password reset by admin {admin_actor.username}",
    )
    db.commit()


def admin_unlock_user(
    db: Session,
    admin_actor: Staff,
    target_staff: Staff,
    admin_role: str,
) -> None:
    """Admin/Owner unlocks a locked staff account."""
    target_staff.locked_at = None
    target_staff.failed_attempts = 0

    log_audit_event(
        db=db,
        tenant_id=admin_actor.tenant_id,
        action="AUTH_ACCOUNT_UNLOCKED",
        entity_type="STAFF",
        entity_id=target_staff.id,
        acting_role=admin_role,
        actor_id=admin_actor.id,
        after_value=f"Account unlocked by admin {admin_actor.username}",
    )
    db.commit()

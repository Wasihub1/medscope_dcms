"""
Prompt 10D Part 5 — User management service (Create User tab / user list).

Safety rules (all enforced here, server side):
- one login = one fixed role (single staff_roles row kept in sync with staff.role);
- a user cannot change their own role, permissions or active state;
- only an OWNER may create, modify or assign the OWNER role (no escalation by ADMIN);
- nobody can grant a permission they do not hold themselves (no escalation);
- the last active user holding 'user.manage' cannot be deactivated, demoted or lose 'user.manage';
- money permissions can never be granted to LAB_TECH or DOCTOR (absolute);
- lab_section is only valid for, and required for, LAB_TECH (Prompt 10E);
- a LAB_TECH created, reactivated or moved into a room releases that room's UNASSIGNED orders;
- every action writes an audit_logs row; passwords are hashed and never returned or logged.
"""
from typing import Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.referrer import Referrer
from backend.app.core.lab_sections import LAB_SECTIONS, is_valid_lab_section, lab_section_label
from backend.app.core.permissions import (
    MONEY_PERMISSIONS,
    MONEY_RESTRICTED_ROLES,
    PERMISSIONS,
    ROLE_DEFAULTS,
    ROLES,
    default_permissions,
    effective_permissions,
    is_grant_allowed,
    normalize_role,
)
from backend.app.core.security import CurrentActor
from backend.app.core.soft_delete import audit_text_with_reason, clean_reason
from backend.app.core.timezone import utc_now
from backend.app.models.user import Staff, StaffPermissionOverride, StaffRole
from backend.app.schemas.user_admin import (
    LabSectionResponse,
    PermissionDefResponse,
    UserAdminMetaResponse,
    UserCreateRequest,
    UserDetailResponse,
    UserPermissionsResponse,
    UserSummaryResponse,
    UserUpdateRequest,
)
from backend.app.schemas.soft_delete import DeletedItemResponse
from backend.app.services.audit_service import log_audit_event
from backend.app.services.routing_service import apply_technician_room_change
from backend.app.services.auth_service import (
    hash_password,
    revoke_all_user_sessions,
    validate_password_strength,
)


def _bad(detail: str, code: int = status.HTTP_400_BAD_REQUEST):
    raise HTTPException(status_code=code, detail=detail)


def get_meta() -> UserAdminMetaResponse:
    return UserAdminMetaResponse(
        roles=list(ROLES),
        permissions=[
            PermissionDefResponse(key=d.key, label=d.label, group=d.group, exposes_money=d.exposes_money)
            for d in PERMISSIONS.values()
        ],
        role_defaults={r: sorted(p) for r, p in ROLE_DEFAULTS.items()},
        money_restricted_roles=sorted(MONEY_RESTRICTED_ROLES),
        lab_sections=[
            LabSectionResponse(code=c, name=v["name"], room=v["room"], label=lab_section_label(c) or c)
            for c, v in LAB_SECTIONS.items()
        ],
    )


def _overrides_of(db: Session, staff_id: int) -> Dict[str, bool]:
    rows = db.execute(
        select(StaffPermissionOverride.permission_key, StaffPermissionOverride.granted).where(
            StaffPermissionOverride.staff_id == staff_id
        )
    ).all()
    return {k: g for k, g in rows}


def _effective_for(db: Session, staff: Staff, role: Optional[str] = None, overrides: Optional[Dict[str, bool]] = None):
    return effective_permissions(role or staff.role, _overrides_of(db, staff.id) if overrides is None else overrides)


def _doctor_profile_name(db: Session, s: Staff) -> Optional[str]:
    if not getattr(s, "doctor_profile_id", None):
        return None
    r = db.get(Referrer, s.doctor_profile_id)
    return r.name if r else None


def _validate_doctor_profile(db: Session, tenant_id: str, role: str, doctor_profile_id: Optional[int]) -> Optional[int]:
    """Prompt 15: only a DOCTOR login links to a doctor profile (a referrers row of this tenant)."""
    if not doctor_profile_id:
        return None
    if role != "DOCTOR":
        _bad("A doctor profile can only be linked to a DOCTOR user.")
    r = db.get(Referrer, doctor_profile_id)
    if r is None or r.tenant_id != tenant_id or r.deleted_at is not None:
        _bad("Doctor profile not found.")
    return r.id


def _summary(db: Session, s: Staff) -> UserSummaryResponse:
    return UserSummaryResponse(
        doctor_profile_id=s.doctor_profile_id,
        doctor_profile_name=_doctor_profile_name(db, s),
        id=s.id,
        username=s.username,
        display_name=s.display_name,
        role=s.role,
        department=s.department,
        lab_section=s.lab_section,
        lab_section_label=lab_section_label(s.lab_section),
        email=s.email,
        phone=s.phone,
        active=s.active,
        is_locked=s.locked_at is not None,
        last_login_at=s.last_login_at,
        override_count=len(_overrides_of(db, s.id)),
    )


def get_user_detail(db: Session, s: Staff) -> UserDetailResponse:
    overrides = _overrides_of(db, s.id)
    return UserDetailResponse(
        **_summary(db, s).model_dump(),
        permissions=UserPermissionsResponse(
            role=s.role,
            defaults=sorted(default_permissions(s.role)),
            overrides=overrides,
            effective=sorted(effective_permissions(s.role, overrides)),
        ),
    )


def list_users(db: Session, tenant_id: str) -> List[UserSummaryResponse]:
    staff = db.execute(
        select(Staff).where(Staff.tenant_id == tenant_id, Staff.deleted_at.is_(None)).order_by(Staff.id)
    ).scalars().all()
    return [_summary(db, s) for s in staff]


def get_user(db: Session, tenant_id: str, user_id: int) -> Staff:
    s = db.get(Staff, user_id)
    if not s or s.tenant_id != tenant_id:
        _bad("User not found.", status.HTTP_404_NOT_FOUND)
    return s


# ---------------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------------
def _validate_role(role: str) -> str:
    r = normalize_role(role)
    if r not in ROLES:
        _bad(f"Unknown role '{role}'. Valid roles: {', '.join(ROLES)}.")
    return r


def _validate_lab_section(role: str, lab_section: Optional[str]) -> Optional[str]:
    if not lab_section:
        if role == "LAB_TECH":
            # Prompt 10E Part 7: a technician always belongs to a room
            _bad("A LAB_TECH user must belong to a lab room. Choose the lab section.")
        return None
    if not is_valid_lab_section(lab_section):
        _bad(f"Unknown lab section '{lab_section}'.")
    if role != "LAB_TECH":
        _bad("A lab section can only be set for LAB_TECH users.")
    return lab_section


def _forbid_self(actor: CurrentActor, target: Staff, what: str) -> None:
    if actor.id == target.id:
        _bad(f"You cannot change your own {what}.", status.HTTP_403_FORBIDDEN)


def _guard_owner_escalation(actor: CurrentActor, target_role_now: Optional[str], new_role: Optional[str]) -> None:
    """Only an OWNER may create/modify OWNER accounts or assign the OWNER role."""
    if actor.role != "OWNER" and ("OWNER" in (target_role_now, new_role)):
        _bad("Only an Owner can create, modify or assign the Owner role.", status.HTTP_403_FORBIDDEN)


def _guard_grant_escalation(actor: CurrentActor, keys: Iterable[str]) -> None:
    missing = [k for k in keys if k not in actor.permissions]
    if missing:
        _bad(f"You cannot grant permissions you do not hold yourself: {', '.join(sorted(missing))}.", status.HTTP_403_FORBIDDEN)


def _guard_money_for_role(role: str, overrides: Dict[str, Optional[bool]]) -> None:
    blocked = [k for k, v in overrides.items() if v and not is_grant_allowed(role, k)]
    if blocked:
        _bad(
            f"Money permissions can never be granted to {role}: {', '.join(sorted(blocked))}.",
            status.HTTP_400_BAD_REQUEST,
        )


def _count_active_user_admins(db: Session, tenant_id: str, exclude_id: Optional[int] = None) -> int:
    staff = db.execute(select(Staff).where(Staff.tenant_id == tenant_id, Staff.active == True)).scalars().all()
    n = 0
    for s in staff:
        if exclude_id is not None and s.id == exclude_id:
            continue
        if "user.manage" in _effective_for(db, s):
            n += 1
    return n


def _guard_last_admin(db: Session, target: Staff, will_have_user_manage: bool, will_be_active: bool) -> None:
    currently = target.active and "user.manage" in _effective_for(db, target)
    if currently and not (will_have_user_manage and will_be_active):
        if _count_active_user_admins(db, target.tenant_id, exclude_id=target.id) == 0:
            _bad(
                "This is the last active user who can manage users. Keep at least one active Admin/Owner with 'user.manage'.",
                status.HTTP_409_CONFLICT,
            )


def _sync_single_role(db: Session, staff: Staff, role: str) -> None:
    rows = db.execute(select(StaffRole).where(StaffRole.staff_id == staff.id)).scalars().all()
    if rows:
        rows[0].role = role
        rows[0].is_primary = True
        for extra in rows[1:]:  # cannot exist under uq_staff_roles_staff_id; defensive only
            db.delete(extra)
    else:
        db.add(StaffRole(staff_id=staff.id, role=role, is_primary=True, created_at=utc_now()))
    staff.role = role


def _audit(db: Session, actor: CurrentActor, action: str, target_id: int, before: Optional[str], after: Optional[str]) -> None:
    log_audit_event(
        db=db,
        tenant_id=actor.tenant_id,
        action=action,
        entity_type="STAFF",
        entity_id=target_id,
        acting_role=actor.role,
        actor_id=actor.id,
        before_value=before,
        after_value=after,
    )


def _apply_overrides(db: Session, actor: CurrentActor, staff: Staff, overrides: Dict[str, Optional[bool]]) -> None:
    for key, granted in overrides.items():
        row = db.execute(
            select(StaffPermissionOverride).where(
                StaffPermissionOverride.staff_id == staff.id, StaffPermissionOverride.permission_key == key
            )
        ).scalar_one_or_none()
        if granted is None:
            if row:
                db.delete(row)
            continue
        if row:
            row.granted = bool(granted)
            row.changed_by_id = actor.id
            row.changed_at = utc_now()
        else:
            db.add(StaffPermissionOverride(
                tenant_id=staff.tenant_id,
                staff_id=staff.id,
                permission_key=key,
                granted=bool(granted),
                changed_by_id=actor.id,
                changed_at=utc_now(),
            ))
    db.flush()


def _validate_override_keys(overrides: Dict[str, Optional[bool]]) -> None:
    unknown = [k for k in overrides if k not in PERMISSIONS]
    if unknown:
        _bad(f"Unknown permission keys: {', '.join(sorted(unknown))}.")


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
def create_user(db: Session, actor: CurrentActor, data: UserCreateRequest) -> Staff:
    role = _validate_role(data.role)
    _guard_owner_escalation(actor, None, role)
    lab_section = _validate_lab_section(role, data.lab_section)
    doctor_profile_id = _validate_doctor_profile(db, actor.tenant_id, role, data.doctor_profile_id)
    username = data.username.strip()
    if db.execute(select(Staff.id).where(func.lower(Staff.username) == username.lower())).first():
        _bad(f"Username '{username}' already exists.", status.HTTP_409_CONFLICT)
    validate_password_strength(data.password, username)
    _validate_override_keys(data.permission_overrides)
    _guard_money_for_role(role, data.permission_overrides)
    _guard_grant_escalation(actor, [k for k, v in data.permission_overrides.items() if v])

    staff = Staff(
        tenant_id=actor.tenant_id,
        username=username,
        display_name=data.display_name.strip(),
        role=role,
        department=(data.department or None),
        lab_section=lab_section,
        doctor_profile_id=doctor_profile_id,
        email=data.email or None,
        phone=data.phone or None,
        active=data.active,
        password_hash=hash_password(data.password),
        password_changed_at=utc_now(),
        failed_attempts=0,
    )
    db.add(staff)
    db.flush()
    _sync_single_role(db, staff, role)
    if data.permission_overrides:
        _apply_overrides(db, actor, staff, data.permission_overrides)
    _audit(db, actor, "USER_CREATED", staff.id, None,
           f"username={staff.username}, role={role}, lab_section={lab_section}, active={staff.active}, overrides={sorted(data.permission_overrides.items())}")
    db.flush()
    _apply_room_change(db, actor, staff, (None, False), "technician created")
    return staff


def _room_state(staff: Staff):
    """(lab_section, counts) where counts = the user is an active LAB_TECH of that room."""
    return staff.lab_section, bool(
        staff.role == "LAB_TECH" and staff.active and staff.deleted_at is None and staff.lab_section
    )


def _apply_room_change(db: Session, actor: CurrentActor, staff: Staff, before, why: str):
    """Prompt 10E Part 7.4 + Prompt 10F (A11): after a staff change (already flushed), the room the
    user left is checked for emptiness (assigned-only orders -> UNASSIGNED) and the room the user
    joined releases its UNASSIGNED orders. Same transaction as the user change; one audit row per
    order (ORDER_UNASSIGNED_ROOM_EMPTY / ORDER_ROOM_RELEASED)."""
    old_section, old_counts = before
    new_section, new_counts = _room_state(staff)
    return apply_technician_room_change(
        db, staff.tenant_id, old_section, old_counts, new_section, new_counts,
        actor.id, actor.role, f"{staff.username}, {why}",
    )


def update_user(db: Session, actor: CurrentActor, staff: Staff, data: UserUpdateRequest) -> Staff:
    _guard_owner_escalation(actor, staff.role, None)
    room_before = _room_state(staff)
    before = f"display_name={staff.display_name}, department={staff.department}, lab_section={staff.lab_section}, email={staff.email}, phone={staff.phone}"
    fields = data.model_dump(exclude_unset=True)
    section_changed = False
    if "lab_section" in fields:
        if actor.id == staff.id:
            _forbid_self(actor, staff, "lab section")
        new_section = _validate_lab_section(staff.role, fields.pop("lab_section"))
        section_changed = new_section != staff.lab_section
        staff.lab_section = new_section
    if "doctor_profile_id" in fields:
        new_profile = _validate_doctor_profile(db, staff.tenant_id, staff.role, fields.pop("doctor_profile_id"))
        if new_profile != staff.doctor_profile_id:
            _audit(db, actor, "USER_DOCTOR_PROFILE_CHANGED", staff.id, str(staff.doctor_profile_id), str(new_profile))
        staff.doctor_profile_id = new_profile
    for k, v in fields.items():
        if k == "display_name" and v is not None:
            staff.display_name = v.strip()
        elif k in ("department", "email", "phone"):
            setattr(staff, k, v or None)
    after = f"display_name={staff.display_name}, department={staff.department}, lab_section={staff.lab_section}, email={staff.email}, phone={staff.phone}"
    _audit(db, actor, "USER_UPDATED", staff.id, before, after)
    db.flush()
    if section_changed:
        _apply_room_change(db, actor, staff, room_before, "room changed")
    return staff


def set_user_role(db: Session, actor: CurrentActor, staff: Staff, role: str, lab_section: Optional[str]) -> Staff:
    _forbid_self(actor, staff, "role")
    new_role = _validate_role(role)
    _guard_owner_escalation(actor, staff.role, new_role)
    new_section = _validate_lab_section(new_role, lab_section) if new_role == "LAB_TECH" else None
    overrides = _overrides_of(db, staff.id)
    new_effective = effective_permissions(new_role, overrides)
    _guard_last_admin(db, staff, "user.manage" in new_effective, staff.active)
    old_role = staff.role
    room_before = _room_state(staff)
    _sync_single_role(db, staff, new_role)
    staff.lab_section = new_section
    if new_role != "DOCTOR":
        staff.doctor_profile_id = None  # Prompt 15: the link only makes sense for a DOCTOR login
    if new_role in MONEY_RESTRICTED_ROLES:
        # Drop money grants that can no longer apply (they would be ignored anyway)
        _apply_overrides(db, actor, staff, {k: None for k, v in overrides.items() if v and k in MONEY_PERMISSIONS})
    revoke_all_user_sessions(db, staff.id, commit=False)  # new role takes effect on next login
    _audit(db, actor, "USER_ROLE_CHANGED", staff.id, old_role, f"{new_role} (lab_section={new_section})")
    db.flush()
    _apply_room_change(db, actor, staff, room_before, f"role changed to {new_role}")
    return staff


def set_user_active(db: Session, actor: CurrentActor, staff: Staff, active: bool) -> Staff:
    _forbid_self(actor, staff, "active status")
    _guard_owner_escalation(actor, staff.role, None)
    if active and staff.deleted_at is not None:
        _bad("This user is deleted. Restore the user first (Deleted users), then reactivate.", status.HTTP_409_CONFLICT)
    if not active:
        _guard_last_admin(db, staff, True, False)
    if staff.active == active:
        return staff
    room_before = _room_state(staff)
    staff.active = active
    if not active:
        revoke_all_user_sessions(db, staff.id, commit=False)
    _audit(db, actor, "USER_REACTIVATED" if active else "USER_DEACTIVATED", staff.id, str(not active), str(active))
    db.flush()
    _apply_room_change(db, actor, staff, room_before, "reactivated" if active else "deactivated")
    return staff


def reset_user_password(db: Session, actor: CurrentActor, staff: Staff, new_password: str) -> None:
    _guard_owner_escalation(actor, staff.role, None)
    validate_password_strength(new_password, staff.username)
    staff.password_hash = hash_password(new_password)
    staff.password_changed_at = utc_now()
    staff.failed_attempts = 0
    staff.locked_at = None
    revoke_all_user_sessions(db, staff.id, commit=False)
    _audit(db, actor, "USER_PASSWORD_RESET", staff.id, None, f"Password reset by {actor.username} (value not logged)")
    db.flush()


def set_user_permissions(db: Session, actor: CurrentActor, staff: Staff, overrides: Dict[str, Optional[bool]]) -> Staff:
    _forbid_self(actor, staff, "permissions")
    _guard_owner_escalation(actor, staff.role, None)
    _validate_override_keys(overrides)
    _guard_money_for_role(staff.role, overrides)
    _guard_grant_escalation(actor, [k for k, v in overrides.items() if v])
    merged = dict(_overrides_of(db, staff.id))
    for k, v in overrides.items():
        if v is None:
            merged.pop(k, None)
        else:
            merged[k] = bool(v)
    _guard_last_admin(db, staff, "user.manage" in effective_permissions(staff.role, merged), staff.active)
    before = str(sorted(_overrides_of(db, staff.id).items()))
    _apply_overrides(db, actor, staff, overrides)
    _audit(db, actor, "USER_PERMISSIONS_CHANGED", staff.id, before, str(sorted(merged.items())))
    db.flush()
    return staff


# ---------------------------------------------------------------------------
# Prompt 11: soft delete / restore (separate from deactivate)
# ---------------------------------------------------------------------------
def delete_user(db: Session, actor: CurrentActor, staff: Staff, reason: Optional[str]) -> Staff:
    """Soft delete: reason required; same guards as deactivate (no self, Owner-only for Owner
    accounts, last active user-manager protected). A deleted user is also forced inactive, so the
    existing 10F room-emptying routine, session revocation and login gate all apply; `deleted_at`
    is additionally checked at login/session so a deleted user never works even if flagged active.
    History, audit rows and assigned past work stay exactly as they are."""
    text = clean_reason(reason)
    _forbid_self(actor, staff, "account (you cannot delete yourself)")
    _guard_owner_escalation(actor, staff.role, None)
    if staff.deleted_at is not None:
        _bad("This user is already deleted.", status.HTTP_409_CONFLICT)
    _guard_last_admin(db, staff, True, False)
    room_before = _room_state(staff)
    was_active = staff.active
    staff.deleted_at = utc_now()
    staff.deleted_by_id = actor.id
    staff.delete_reason = text
    staff.active = False
    revoke_all_user_sessions(db, staff.id, commit=False)
    _audit(db, actor, "USER_SOFT_DELETED", staff.id,
           f"username={staff.username}, role={staff.role}, active={was_active}",
           audit_text_with_reason("Soft-deleted; forced inactive", text))
    db.flush()
    _apply_room_change(db, actor, staff, room_before, "deleted")
    return staff


def restore_user(db: Session, actor: CurrentActor, staff: Staff) -> Staff:
    """Clears the delete fields. The user stays INACTIVE (delete forced it); an Admin/Owner then
    uses Reactivate, which runs the normal release-on-join. Restore itself moves no orders."""
    _guard_owner_escalation(actor, staff.role, None)
    if staff.deleted_at is None:
        _bad("This user is not deleted.", status.HTTP_409_CONFLICT)
    before = audit_text_with_reason(
        f"Deleted at {staff.deleted_at.isoformat()} by staff {staff.deleted_by_id}", staff.delete_reason
    )
    staff.deleted_at = None
    staff.deleted_by_id = None
    staff.delete_reason = None
    _audit(db, actor, "USER_RESTORED", staff.id, before, "Restored (still inactive; reactivate to allow login)")
    db.flush()
    return staff


def list_deleted_users(db: Session, tenant_id: str) -> List[DeletedItemResponse]:
    from backend.app.services.soft_delete_service import staff_names

    rows = db.execute(
        select(Staff).where(Staff.tenant_id == tenant_id, Staff.deleted_at.is_not(None)).order_by(Staff.deleted_at.desc())
    ).scalars().all()
    names = staff_names(db, [r.deleted_by_id for r in rows])
    return [
        DeletedItemResponse(
            id=r.id, kind="USER", title=f"{r.display_name} ({r.username})",
            subtitle=" · ".join(x for x in (r.role, lab_section_label(r.lab_section)) if x),
            deleted_at=r.deleted_at, deleted_by_id=r.deleted_by_id,
            deleted_by_name=names.get(r.deleted_by_id), delete_reason=r.delete_reason,
        )
        for r in rows
    ]

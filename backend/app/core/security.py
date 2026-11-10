from typing import Optional
from fastapi import Header, HTTPException, Depends, status
from pydantic import BaseModel


class CurrentActor(BaseModel):
    id: int
    tenant_id: str
    username: str
    display_name: str
    role: str  # RECEPTIONIST, ADMIN, OWNER, etc.
    email: Optional[str] = None
    phone: Optional[str] = None


# Default development actors
DEFAULT_RECEPTIONIST = CurrentActor(
    id=1,
    tenant_id="center-seba-01",
    username="reception_fatima",
    display_name="Fatima Akter",
    role="RECEPTIONIST",
    email="fatima@sebadiagnostic.com",
    phone="01711000111",
)

DEFAULT_ADMIN = CurrentActor(
    id=2,
    tenant_id="center-seba-01",
    username="admin_tariq",
    display_name="Tariqul Islam (Admin)",
    role="ADMIN",
    email="tariq@sebadiagnostic.com",
    phone="01711000222",
)

DEFAULT_TECH_KAMAL = CurrentActor(
    id=3,
    tenant_id="center-seba-01",
    username="tech_kamal",
    display_name="Kamal Hossain (Hematology)",
    role="LAB_TECH",
    email="kamal@sebadiagnostic.com",
    phone="01711000333",
)

DEFAULT_TECH_NASRIN = CurrentActor(
    id=4,
    tenant_id="center-seba-01",
    username="tech_nasrin",
    display_name="Nasrin Sultana (Biochemistry)",
    role="LAB_TECH",
    email="nasrin@sebadiagnostic.com",
    phone="01711000444",
)


def get_current_actor(
    x_actor_role: Optional[str] = Header(default=None, alias="X-Actor-Role"),
    x_staff_role: Optional[str] = Header(default=None, alias="X-Staff-Role"),
    x_actor_id: Optional[str] = Header(default=None, alias="X-Actor-Id"),
    x_staff_id: Optional[str] = Header(default=None, alias="X-Staff-Id"),
    x_tenant_id: Optional[str] = Header(default="center-seba-01", alias="X-Tenant-Id"),
) -> CurrentActor:
    """Dependency returning the current development actor based on request headers."""
    raw_role = x_actor_role or x_staff_role or "RECEPTIONIST"
    role_normalized = raw_role.strip().upper()
    tenant = (x_tenant_id or "center-seba-01").strip()
    if not tenant or tenant == "11111111-1111-1111-1111-111111111111":
        tenant = "center-seba-01"

    raw_id = x_actor_id or x_staff_id or "1"
    # Safely resolve numeric staff ID
    staff_id = None
    if raw_id:
        try:
            staff_id = int(str(raw_id).strip())
        except (ValueError, TypeError):
            staff_id = None
    if x_actor_id:
        try:
            staff_id = int(str(x_actor_id).strip())
        except (ValueError, TypeError):
            staff_id = None

    if role_normalized in ("ADMIN", "OWNER"):
        return CurrentActor(
            id=staff_id if staff_id is not None else 2,
            tenant_id=tenant,
            username="admin_tariq",
            display_name="Tariqul Islam (Admin)",
            role="ADMIN",
            email="tariq@sebadiagnostic.com",
            phone="01711000222",
        )
    elif role_normalized == "LAB_TECH":
        if staff_id == 4:
            return CurrentActor(
                id=4,
                tenant_id=tenant,
                username="tech_nasrin",
                display_name="Nasrin Sultana (Biochemistry)",
                role="LAB_TECH",
                email="nasrin@sebadiagnostic.com",
                phone="01711000444",
            )
        return CurrentActor(
            id=3 if staff_id is None else staff_id,
            tenant_id=tenant,
            username="tech_kamal",
            display_name="Kamal Hossain (Hematology)",
            role="LAB_TECH",
            email="kamal@sebadiagnostic.com",
            phone="01711000333",
        )
    return CurrentActor(
        id=staff_id if staff_id is not None else 1,
        tenant_id=tenant,
        username="reception_fatima",
        display_name="Fatima Akter",
        role="RECEPTIONIST",
        email="fatima@sebadiagnostic.com",
        phone="01711000111",
    )


def require_receptionist(
    actor: CurrentActor = Depends(get_current_actor),
) -> CurrentActor:
    """Ensures actor is permitted to perform Receptionist operations."""
    if actor.role not in ("RECEPTIONIST", "ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to Receptionist, Admin, or Owner roles.",
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

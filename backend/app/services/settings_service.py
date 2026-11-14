"""Prompt 17: owner-editable center settings. Known keys, defaults and validation live here;
a missing row means the default, so existing behavior is unchanged until the Owner edits a value."""
from typing import Dict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.timezone import utc_now
from backend.app.models.dues import TenantSetting
from backend.app.services.audit_service import log_audit_event

DEFAULTS: Dict[str, str] = {
    # Hold a finished report while its invoice has a due (Module 17). On = the behavior before Prompt 17.
    "report_hold_when_due": "true",
    # Largest amount (whole Taka, per invoice in total) an Admin may write off alone (D11). Owner has no limit.
    "writeoff_admin_limit": "500",
    # Prompt 18 (D46): largest day-close variance (whole Taka, either direction) that needs no reason. 0 = every variance needs one.
    "cash_variance_tolerance": "0",
}


def _raw(db: Session, tenant_id: str, key: str) -> str:
    row = db.execute(select(TenantSetting).where(TenantSetting.tenant_id == tenant_id, TenantSetting.key == key)).scalar_one_or_none()
    return row.value if row is not None else DEFAULTS[key]


def get_bool(db: Session, tenant_id: str, key: str) -> bool:
    return _raw(db, tenant_id, key).strip().lower() == "true"


def get_int(db: Session, tenant_id: str, key: str) -> int:
    return int(_raw(db, tenant_id, key))


def get_all(db: Session, tenant_id: str) -> dict:
    return {
        "report_hold_when_due": get_bool(db, tenant_id, "report_hold_when_due"),
        "writeoff_admin_limit": get_int(db, tenant_id, "writeoff_admin_limit"),
        "cash_variance_tolerance": get_int(db, tenant_id, "cash_variance_tolerance"),
    }


def update(db: Session, actor, changes: dict) -> dict:
    """Owner edit. Every changed value is audited (old and new)."""
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown setting '{key}'.")
        if key in ("writeoff_admin_limit", "cash_variance_tolerance"):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be a whole number of Taka, 0 or more.")
            new = str(value)
        else:
            if not isinstance(value, bool):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be true or false.")
            new = "true" if value else "false"
        old = _raw(db, actor.tenant_id, key)
        if old == new:
            continue
        row = db.execute(select(TenantSetting).where(TenantSetting.tenant_id == actor.tenant_id, TenantSetting.key == key)).scalar_one_or_none()
        if row is None:
            db.add(TenantSetting(tenant_id=actor.tenant_id, key=key, value=new, updated_by_id=actor.id, updated_at=utc_now()))
        else:
            row.value, row.updated_by_id, row.updated_at = new, actor.id, utc_now()
        log_audit_event(db=db, tenant_id=actor.tenant_id, action="SETTING_CHANGED", entity_type="SETTING", entity_id=key,
                        acting_role=actor.role, actor_id=actor.id, before_value=old, after_value=new)
    db.flush()
    return get_all(db, actor.tenant_id)

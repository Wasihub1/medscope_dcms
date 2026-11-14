"""Prompt 17: owner-editable center settings (report hold while due, Admin write-off limit)."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor, get_current_actor
from backend.app.services import settings_service

router = APIRouter()


class SettingsResponse(BaseModel):
    report_hold_when_due: bool
    writeoff_admin_limit: int
    cash_variance_tolerance: int


class SettingsUpdate(BaseModel):
    report_hold_when_due: Optional[bool] = None
    writeoff_admin_limit: Optional[int] = Field(default=None, ge=0)
    cash_variance_tolerance: Optional[int] = Field(default=None, ge=0)


@router.get("", response_model=SettingsResponse, summary="Read the center settings (any signed-in role; they contain no secrets)")
def read_settings(actor: CurrentActor = Depends(get_current_actor), db: Session = Depends(get_db)):
    return settings_service.get_all(db, actor.tenant_id)


@router.put("", response_model=SettingsResponse, summary="Edit center settings (Owner)")
def update_settings(data: SettingsUpdate, actor: CurrentActor = Depends(require_permission("settings.manage")), db: Session = Depends(get_db)):
    res = settings_service.update(db, actor, data.model_dump(exclude_unset=True, exclude_none=True))
    db.commit()
    return res

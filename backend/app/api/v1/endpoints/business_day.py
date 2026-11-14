from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, get_current_actor
from backend.app.core.permissions import require_permission
from backend.app.schemas.business_day import (
    BusinessDayStatusResponse,
    BusinessDayOpenRequest,
    BusinessDayState,
)
from backend.app.services.business_day_service import (
    get_business_day_status,
    get_business_day_state,
    open_business_day,
)
from backend.app.services import day_close_service

router = APIRouter()


class BusinessDayCloseRequest(BaseModel):
    """Prompt 18: counted cash is required (D46); other channels are counted on their own lines."""
    counted_cash: int = Field(ge=0)
    counted_channels: Dict[str, int] = {}
    variance_reason: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = None
    day_id: Optional[int] = None  # only to re-close a reopened day


class MovementRequest(BaseModel):
    kind: str
    amount: int
    note: Optional[str] = Field(default=None, max_length=300)


class ReopenRequest(BaseModel):
    reason: str = Field(max_length=300)


class AdjustmentRequest(BaseModel):
    reason: str = Field(max_length=300)
    reverse_entry_id: Optional[int] = None
    lines: Optional[List[Dict[str, Any]]] = None


@router.get("/state", response_model=BusinessDayState, summary="Open/closed state of the business day, no money fields (every authenticated role, incl. Lab Tech)")
def get_state(
    actor: CurrentActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    return get_business_day_state(db, actor.tenant_id)


@router.get("/status", response_model=BusinessDayStatusResponse, summary="Get current Business Day status and channel balances")
@router.get("/current", response_model=BusinessDayStatusResponse, summary="Get current Business Day status (alias for /status)")
def get_status(
    actor: CurrentActor = Depends(require_permission("business_day.view")),
    db: Session = Depends(get_db),
):
    return get_business_day_status(db, actor.tenant_id)


@router.post("/open", response_model=BusinessDayStatusResponse, status_code=status.HTTP_201_CREATED, summary="Open a new Business Day session")
def open_day(
    data: BusinessDayOpenRequest,
    actor: CurrentActor = Depends(require_permission("business_day.open")),
    db: Session = Depends(get_db),
):
    open_business_day(
        db=db,
        tenant_id=actor.tenant_id,
        data=data,
        opener_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    return get_business_day_status(db, actor.tenant_id)


@router.post("/close", response_model=BusinessDayStatusResponse, summary="Close Business Day with counted cash (Admin/Owner only; Rejected for Receptionist/Cashier)")
def close_day(
    data: BusinessDayCloseRequest,
    actor: CurrentActor = Depends(require_permission("business_day.close")),
    db: Session = Depends(get_db),
):
    counted = {"CASH": data.counted_cash, **data.counted_channels}
    day_close_service.close_day(db, actor, counted, data.variance_reason, data.notes, data.day_id)
    db.commit()
    return get_business_day_status(db, actor.tenant_id)


@router.get("/day-screen", summary="Day screen: expected cash (D45), channel lines, movements, tolerance (Admin/Owner)")
def day_screen(actor: CurrentActor = Depends(require_permission("business_day.close")), db: Session = Depends(get_db)):
    return day_close_service.get_day_screen(db, actor.tenant_id)


@router.post("/movements", status_code=status.HTTP_201_CREATED, summary="Bank deposit, owner withdrawal (Owner) or small expense from the open day's cash")
def add_movement(data: MovementRequest, actor: CurrentActor = Depends(require_permission("business_day.close")), db: Session = Depends(get_db)):
    res = day_close_service.record_movement(db, actor, data.kind, data.amount, data.note)
    db.commit()
    return res


@router.post("/{day_id}/reopen", summary="Reopen a closed day for adjusting entries only (Owner, reason required)")
def reopen(day_id: int, data: ReopenRequest, actor: CurrentActor = Depends(require_permission("business_day.close")), db: Session = Depends(get_db)):
    day = day_close_service.reopen_day(db, actor, day_id, data.reason)
    db.commit()
    return {"id": day.id, "day_number": day.day_number, "status": day.status}


@router.post("/{day_id}/adjustments", status_code=status.HTTP_201_CREATED, summary="Adjusting journal entry on a reopened day (Owner): a reversal or a balanced manual entry")
def adjust(day_id: int, data: AdjustmentRequest, actor: CurrentActor = Depends(require_permission("business_day.close")), db: Session = Depends(get_db)):
    entry = day_close_service.post_adjustment(db, actor, day_id, data.reverse_entry_id, data.lines, data.reason)
    db.commit()
    return {"entry_id": entry.id}

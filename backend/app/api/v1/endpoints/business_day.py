from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.schemas.business_day import (
    BusinessDayStatusResponse,
    BusinessDayOpenRequest,
)
from backend.app.services.business_day_service import (
    get_business_day_status,
    open_business_day,
    close_business_day,
    reject_close_business_day_for_receptionist,
)

router = APIRouter()


class BusinessDayCloseRequest(BaseModel):
    notes: Optional[str] = None


@router.get("/status", response_model=BusinessDayStatusResponse, summary="Get current Business Day status and channel balances")
@router.get("/current", response_model=BusinessDayStatusResponse, summary="Get current Business Day status (alias for /status)")
def get_status(
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return get_business_day_status(db, actor.tenant_id)


@router.post("/open", response_model=BusinessDayStatusResponse, status_code=status.HTTP_201_CREATED, summary="Open a new Business Day session")
def open_day(
    data: BusinessDayOpenRequest,
    actor: CurrentActor = Depends(require_receptionist),
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


@router.post("/close", response_model=BusinessDayStatusResponse, summary="Close Business Day (Admin/Owner only; Rejected for Receptionist/Cashier)")
def close_day(
    data: Optional[BusinessDayCloseRequest] = None,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    close_business_day(
        db=db,
        tenant_id=actor.tenant_id,
        closer_id=actor.id,
        acting_role=actor.role,
        notes=data.notes if data else None,
    )
    db.commit()
    return get_business_day_status(db, actor.tenant_id)


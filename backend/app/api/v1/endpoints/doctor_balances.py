"""Prompt 17 (D43): a doctor's two separate balances (read only)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import require_permission
from backend.app.core.security import CurrentActor
from backend.app.services import dues_service

router = APIRouter()


@router.get("", summary="Per doctor: wholesale receivable and professional-fee payable, kept apart (Admin/Owner)")
def get_doctor_balances(actor: CurrentActor = Depends(require_permission("doctor_balance.view")), db: Session = Depends(get_db)):
    return dues_service.doctor_balances(db, actor.tenant_id)

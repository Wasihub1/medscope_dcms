from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.schemas.dashboard import ReceptionistDashboardResponse
from backend.app.services.dashboard_service import get_receptionist_dashboard_data

router = APIRouter()


@router.get("", response_model=ReceptionistDashboardResponse, summary="Get Receptionist Bento Grid Dashboard Data")
def get_dashboard(
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return get_receptionist_dashboard_data(db, actor.tenant_id)


from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.schemas.search import GlobalSearchResponse
from backend.app.services.search_service import execute_global_search

router = APIRouter()


@router.get("", response_model=GlobalSearchResponse, summary="Global Autocomplete Search Bar")
def global_search(
    q: str = Query(..., min_length=1, description="Search query string"),
    actor: CurrentActor = Depends(require_permission("search.use")),
    db: Session = Depends(get_db),
):
    return execute_global_search(db, actor.tenant_id, q)


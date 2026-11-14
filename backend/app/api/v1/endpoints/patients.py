from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission
from backend.app.models.patient import Patient
from backend.app.schemas.patient import (
    PatientCreate,
    PatientResponse,
    PatientHistoryResponse,
    DuplicatePatientCheck,
)
from backend.app.services.patient_service import (
    search_patients,
    check_duplicate_patients,
    create_patient,
    get_patient_history,
)

router = APIRouter()


@router.get("", response_model=List[PatientResponse], summary="Search and list patients")
def list_patients(
    q: Optional[str] = Query(default="", description="Search by name, phone, code"),
    limit: int = Query(default=30, le=100),
    actor: CurrentActor = Depends(require_permission("patient.view")),
    db: Session = Depends(get_db),
):
    patients = search_patients(db, actor.tenant_id, q, limit=limit)
    return [PatientResponse.model_validate(p) for p in patients]


@router.get("/check-duplicates", response_model=DuplicatePatientCheck, summary="Check duplicate candidates before patient creation")
def check_duplicates(
    name: str = Query(..., min_length=2),
    phone: str = Query(..., min_length=6),
    actor: CurrentActor = Depends(require_permission("patient.view")),
    db: Session = Depends(get_db),
):
    return check_duplicate_patients(db, actor.tenant_id, name, phone)


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED, summary="Create a new patient")
def create_new_patient(
    data: PatientCreate,
    actor: CurrentActor = Depends(require_permission("patient.create")),
    db: Session = Depends(get_db),
):
    patient = create_patient(
        db=db,
        tenant_id=actor.tenant_id,
        data=data,
        creator_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(patient)
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientResponse, summary="Get patient details")
def get_patient(
    patient_id: int,
    actor: CurrentActor = Depends(require_permission("patient.view")),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}/history", response_model=PatientHistoryResponse, summary="Get permitted patient front-desk operational history")
def get_history(
    patient_id: int,
    actor: CurrentActor = Depends(require_permission("patient.view")),
    db: Session = Depends(get_db),
):
    history = get_patient_history(db, actor.tenant_id, patient_id)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return history


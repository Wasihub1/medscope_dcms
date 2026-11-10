from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor, require_receptionist
from backend.app.schemas.report import (
    DeliverableReportResponse,
    ReportDeliveryRequest,
    ReportDeliveryResponse,
    PrintableReportData,
)
from backend.app.services.report_service import (
    list_deliverable_reports,
    get_deliverable_report_by_id,
    record_report_delivery,
    get_printable_report_data,
)
from backend.app.services.audit_service import log_reprint_event

router = APIRouter()


@router.get("/deliverable", response_model=List[DeliverableReportResponse], summary="List finalized reports ready for delivery")
@router.get("", response_model=List[DeliverableReportResponse], summary="List finalized reports ready for delivery (alias)")
@router.get("/", response_model=List[DeliverableReportResponse], summary="List finalized reports ready for delivery (alias)")
def get_deliverable_reports(
    q: Optional[str] = Query(default=None, description="Search by report no, invoice no, patient name"),
    delivery_status: Optional[str] = Query(default=None, description="PENDING, DELIVERED, or ALL"),
    limit: int = Query(default=50, le=100),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return list_deliverable_reports(
        db=db,
        tenant_id=actor.tenant_id,
        query=q,
        delivery_status=delivery_status,
        limit=limit,
    )


@router.post("/deliver/{report_version_id}", response_model=ReportDeliveryResponse, status_code=status.HTTP_201_CREATED, summary="Deliver finalized report to patient or relation")
@router.post("/{report_version_id}/deliver", response_model=ReportDeliveryResponse, status_code=status.HTTP_201_CREATED, summary="Deliver report (alias)")
@router.post("/{report_version_id}/override-hold", response_model=ReportDeliveryResponse, status_code=status.HTTP_201_CREATED, summary="Admin due override delivery")
def deliver_report(
    report_version_id: int,
    data: ReportDeliveryRequest,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    # Normalize aliases
    if not data.delivered_to_name and data.recipient_name:
        data.delivered_to_name = data.recipient_name
    if data.recipient_phone:
        data.delivered_to_phone = data.recipient_phone
    if data.recipient_relation:
        data.delivered_to_relation = data.recipient_relation
    if data.override_reason and not data.admin_due_override_reason:
        data.admin_due_override_reason = data.override_reason

    deliv = record_report_delivery(
        db=db,
        tenant_id=actor.tenant_id,
        report_version_id=report_version_id,
        data=data,
        deliverer_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()
    db.refresh(deliv)
    return ReportDeliveryResponse(
        id=deliv.id,
        report_version_id=deliv.report_version_id,
        delivered_to_name=deliv.delivered_to_name,
        delivered_to_phone=deliv.delivered_to_phone,
        delivered_to_relation=deliv.delivered_to_relation,
        delivered_with_due=deliv.delivered_with_due,
        due_release_reason=deliv.due_release_reason,
        delivered_at=deliv.delivered_at,
        delivered_by_name=actor.display_name,
    )


@router.get("/printable/{report_version_id}", response_model=PrintableReportData, summary="Retrieve printable report data and register reprint audit")
def get_printable_report(
    report_version_id: int,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return get_printable_report_data(
        db=db,
        tenant_id=actor.tenant_id,
        report_version_id=report_version_id,
        actor_id=actor.id,
    )


@router.get("/{report_version_id}", response_model=DeliverableReportResponse, summary="Get single deliverable report detail")
def get_report_detail(
    report_version_id: int,
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    return get_deliverable_report_by_id(
        db=db,
        tenant_id=actor.tenant_id,
        report_version_id=report_version_id,
    )


@router.post("/{report_version_id}/print-events", summary="Register print audit event")
def log_report_print_event(
    report_version_id: int,
    reason: Optional[str] = Query(default="Print diagnostic report", description="Print or reprint reason"),
    actor: CurrentActor = Depends(require_receptionist),
    db: Session = Depends(get_db),
):
    log_reprint_event(
        db=db,
        tenant_id=actor.tenant_id,
        entity_type="REPORT",
        entity_id=report_version_id,
        reprinted_by_id=actor.id,
        reason=reason,
    )
    db.commit()
    return {"status": "ok", "report_id": report_version_id}


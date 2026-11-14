from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission, has_permission
from backend.app.schemas.report import (
    DeliverableReportResponse,
    ReportDeliveryRequest,
    ReportDeliveryResponse,
    PrintableReportData,
    ReadyReportResponse,
    ResultPreviewResponse,
)
from backend.app.services.ready_report_service import build_result_preview, list_ready_reports
from backend.app.services.report_service import (
    list_deliverable_reports,
    get_deliverable_report_by_id,
    record_report_delivery,
    get_printable_report_data,
    get_final_snapshot,
    log_report_view,
    log_ready_result_view,
)
from backend.app.services.audit_service import log_reprint_event

router = APIRouter()


@router.get("/deliverable", response_model=List[DeliverableReportResponse], summary="List finalized reports ready for delivery")
@router.get("", response_model=List[DeliverableReportResponse], summary="List finalized reports ready for delivery (alias)")
@router.get("/", response_model=List[DeliverableReportResponse], summary="List finalized reports ready for delivery (alias)")
def get_deliverable_reports(
    q: Optional[str] = Query(default=None, description="Search by report no, bill no (final or temporary), patient no, test, mobile or name"),
    search: Optional[str] = Query(default=None, description="Alias of q"),
    delivery_status: Optional[str] = Query(default=None, description="PENDING, DELIVERED, or ALL"),
    limit: int = Query(default=50, le=100),
    has_due: Optional[bool] = Query(default=None, description="true = invoice has a due, false = no due"),
    actor: CurrentActor = Depends(require_permission("report.view")),
    db: Session = Depends(get_db),
):
    return list_deliverable_reports(
        db=db,
        tenant_id=actor.tenant_id,
        query=q or search,
        delivery_status=delivery_status,
        limit=limit,
        has_due=has_due,
    )


@router.get(
    "/ready",
    response_model=List[ReadyReportResponse],
    response_model_exclude_unset=True,
    summary="List Ready results from all rooms (Prompt 10F; not issued reports)",
)
def get_ready_reports(
    q: Optional[str] = Query(default=None, description="Search patient, phone, invoice no or test"),
    lab_section: Optional[str] = Query(default=None, description="Room code, NONE for orders without a room, or ALL"),
    limit: int = Query(default=100, ge=1, le=200),
    actor: CurrentActor = Depends(require_permission("report.view")),
    db: Session = Depends(get_db),
):
    """Ready = ENTERED result on an order that is not cancelled, not performed or awaiting doctor
    (the one shared definition, also used by the Lab tile and tab). invoice_due / has_due are only
    returned to actors allowed to see money."""
    return list_ready_reports(db, actor.tenant_id, actor, query=q, lab_section=lab_section, limit=limit)


@router.get("/ready/{test_order_id}/preview", response_model=ResultPreviewResponse, summary="Read-only preview of a saved result (Prompt 10F, money-free)")
def get_ready_report_preview(
    test_order_id: int,
    actor: CurrentActor = Depends(require_permission("report.view")),
    db: Session = Depends(get_db),
):
    result = build_result_preview(db, actor.tenant_id, test_order_id)
    log_ready_result_view(db, actor, test_order_id)  # Prompt 19B: report-view logging
    db.commit()
    return result


@router.post("/deliver/{report_version_id}", response_model=ReportDeliveryResponse, status_code=status.HTTP_201_CREATED, summary="Deliver finalized report to patient or relation")
@router.post("/{report_version_id}/deliver", response_model=ReportDeliveryResponse, status_code=status.HTTP_201_CREATED, summary="Deliver report (alias)")
@router.post("/{report_version_id}/override-hold", response_model=ReportDeliveryResponse, status_code=status.HTTP_201_CREATED, summary="Admin due override delivery")
def deliver_report(
    report_version_id: int,
    data: ReportDeliveryRequest,
    actor: CurrentActor = Depends(require_permission("report.deliver")),
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
        can_release_with_due=has_permission(actor, "report.release_with_due"),
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
    actor: CurrentActor = Depends(require_permission("report.deliver")),
    db: Session = Depends(get_db),
):
    data = get_printable_report_data(
        db=db,
        tenant_id=actor.tenant_id,
        report_version_id=report_version_id,
        actor_id=actor.id,
        acting_role=actor.role,
    )
    db.commit()  # Prompt 17: the reprint log row was written but never committed before, so it was lost
    return data


@router.get("/{report_version_id}/snapshot", response_model=ResultPreviewResponse, summary="Stored, immutable content of a Final report (Module 14, money-free)")
def get_report_snapshot(
    report_version_id: int,
    actor: CurrentActor = Depends(require_permission("report.view")),
    db: Session = Depends(get_db),
):
    result = get_final_snapshot(db, actor.tenant_id, report_version_id)
    log_report_view(db, actor, report_version_id, "snapshot")  # Prompt 19B: report-view logging
    db.commit()
    return result


@router.get("/{report_version_id}", response_model=DeliverableReportResponse, summary="Get single deliverable report detail")
def get_report_detail(
    report_version_id: int,
    actor: CurrentActor = Depends(require_permission("report.view")),
    db: Session = Depends(get_db),
):
    result = get_deliverable_report_by_id(
        db=db,
        tenant_id=actor.tenant_id,
        report_version_id=report_version_id,
    )
    log_report_view(db, actor, report_version_id, "report detail")  # Prompt 19B: report-view logging
    db.commit()
    return result


@router.post("/{report_version_id}/print-events", summary="Register print audit event")
def log_report_print_event(
    report_version_id: int,
    reason: Optional[str] = Query(default="Print diagnostic report", description="Print or reprint reason"),
    actor: CurrentActor = Depends(require_permission("report.deliver")),
    db: Session = Depends(get_db),
):
    log_reprint_event(
        db=db,
        tenant_id=actor.tenant_id,
        entity_type="REPORT",
        entity_id=report_version_id,
        actor_id=actor.id,
        acting_role=actor.role,
        reason=reason,
    )
    db.commit()
    return {"status": "ok", "report_id": report_version_id}


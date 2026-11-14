from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import CurrentActor
from backend.app.core.permissions import require_permission, require_any_permission
from backend.app.schemas.worklist import (
    TechnicianWorklistItemResponse,
    SampleTakenRequest,
    RejectSampleRequest,
    PatientContactRequest,
    ImagingPerformedRequest,
    CultureStageRequest,
    OutsourcedStageRequest,
    BarcodeLabelResponse,
    TestOrderEventResponse,
    UpdateOrderStatusRequest,
    WorklistSummaryResponse,
    ReassignRoomRequest,
    RoomResponse,
)
from backend.app.services.worklist_service import (
    get_technician_worklist,
    record_sample_taken,
    record_sample_rejected,
    record_patient_contact,
    record_imaging_performed,
    record_culture_stage,
    record_outsourced_stage,
    get_order_events,
    generate_barcode_label_data,
    update_order_status,
    get_worklist_summary,
)

from backend.app.services.routing_service import list_rooms, move_order_to_room, ensure_order_access
from backend.app.services.ready_report_service import build_result_preview
from backend.app.schemas.report import ResultPreviewResponse
from backend.app.models.test_order import TestOrder

router = APIRouter()


@router.get("/rooms", response_model=List[RoomResponse], summary="List lab rooms with active technician counts (Prompt 10E)")
def get_rooms(
    actor: CurrentActor = Depends(require_any_permission("worklist.view", "worklist.reassign", "assignment.manage")),
    db: Session = Depends(get_db),
):
    return list_rooms(db, actor.tenant_id)


@router.post("/{test_order_id}/reassign", response_model=TechnicianWorklistItemResponse, summary="Move an order to another room before COMPLETED (worklist.reassign)")
def reassign_room(
    test_order_id: int,
    data: ReassignRoomRequest,
    actor: CurrentActor = Depends(require_permission("worklist.reassign")),
    db: Session = Depends(get_db),
):
    from backend.app.services.worklist_service import build_worklist_item
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="Test order not found.")
    move_order_to_room(
        db, actor.tenant_id, order, (data.lab_section or "").strip().upper(), actor.id, actor.role,
        reason=data.reason, action="REASSIGN_ROOM",
    )
    db.commit()
    db.refresh(order)
    return build_worklist_item(order)


@router.get("/{test_order_id}/result-preview", response_model=ResultPreviewResponse, summary="Read-only preview of a saved result, DRAFT or ENTERED (Prompt 10F, money-free)")
def result_preview(
    test_order_id: int,
    actor: CurrentActor = Depends(require_permission("worklist.view")),
    db: Session = Depends(get_db),
):
    """Preview only: no print, no finalize, no report version. Uses the stored result snapshots.
    Room-based access like every other worklist action (technician: own room only)."""
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=404, detail="Test order not found.")
    ensure_order_access(actor, order, "You can only preview results for orders in your room.")
    return build_result_preview(db, actor.tenant_id, test_order_id)


@router.get("", response_model=List[TechnicianWorklistItemResponse], summary="List assigned laboratory operational tasks (Strictly Financial-Free)")
def list_worklist(
    status: Optional[str] = Query(default=None, description="Workflow status filter (e.g. ASSIGNED, SAMPLE_PENDING, IN_PROGRESS, AWAITING_DOCTOR, COMPLETED, REJECTED, CULTURE, IMAGING, OUTSOURCED)"),
    department: Optional[str] = Query(default=None, description="Department filter"),
    urgent_only: bool = Query(default=False, description="Filter only STAT urgent tasks"),
    q: Optional[str] = Query(default=None, description="Barcode, sample code, patient name, MRN, or test query"),
    staff_id: Optional[int] = Query(default=None, description="Supervisor inspection of specific staff queue (Admin/Owner only)"),
    limit: int = Query(default=100, le=200),
    actor: CurrentActor = Depends(require_permission("worklist.view")),
    db: Session = Depends(get_db),
):
    """
    Returns assigned laboratory tasks. Technicians are strictly locked to their own tasks.
    All financial fields are excluded at the schema level per Section 5.4.
    """
    return get_technician_worklist(
        db=db,
        tenant_id=actor.tenant_id,
        actor=actor,
        staff_id=staff_id,
        status_filter=status,
        department_filter=department,
        urgent_only=urgent_only,
        query=q,
        limit=limit,
    )


@router.get("/summary", response_model=WorklistSummaryResponse, summary="Get technician workbench KPI summary tiles")
def get_summary(
    staff_id: Optional[int] = Query(default=None, description="Staff ID for Admin inspection"),
    actor: CurrentActor = Depends(require_permission("worklist.view")),
    db: Session = Depends(get_db),
):
    return get_worklist_summary(
        db=db,
        tenant_id=actor.tenant_id,
        actor=actor,
        staff_id=staff_id,
    )


@router.post("/{test_order_id}/sample-taken", response_model=TechnicianWorklistItemResponse, summary="Record specimen collection event (Quick Route & Full Route)")
def sample_taken(
    test_order_id: int,
    data: SampleTakenRequest,
    actor: CurrentActor = Depends(require_permission("sample.manage")),
    db: Session = Depends(get_db),
):
    """
    Specimen collection: records collection timestamp, creates/updates sample, locks
    invoice line against cancellation, triggers stock deduction boundary, and starts Lab Clock.
    """
    item = record_sample_taken(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item


@router.post("/{test_order_id}/reject-sample", response_model=TechnicianWorklistItemResponse, summary="Record spoiled or rejected specimen (Section 5.3 & D15 rule)")
def reject_sample(
    test_order_id: int,
    data: RejectSampleRequest,
    actor: CurrentActor = Depends(require_permission("sample.manage")),
    db: Session = Depends(get_db),
):
    """
    Controlled rejection of spoiled or unsuitable specimen. Requires mandatory rejection reason.
    Marks task as REJECTED/SPOILED, preserves line lock, and flags patient for follow-up.
    """
    item = record_sample_rejected(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item


@router.post("/{test_order_id}/patient-contact", response_model=TechnicianWorklistItemResponse, summary="Record patient call follow-up after specimen rejection")
def patient_contact(
    test_order_id: int,
    data: PatientContactRequest,
    actor: CurrentActor = Depends(require_permission("worklist.update")),
    db: Session = Depends(get_db),
):
    """
    Records call follow-up outcome with patient for a rejected specimen (D15 rule).
    Enforces that new collection requires a new bill line; no free re-runs.
    """
    item = record_patient_contact(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item


@router.post("/{test_order_id}/imaging-performed", response_model=TechnicianWorklistItemResponse, summary="Record imaging scan execution (Section 5.5)")
def imaging_performed(
    test_order_id: int,
    data: ImagingPerformedRequest,
    actor: CurrentActor = Depends(require_permission("worklist.update")),
    db: Session = Depends(get_db),
):
    """
    Records radiology / imaging scan executed. Locks line for doctor interpretation
    and routes task to AWAITING_DOCTOR queue.
    """
    item = record_imaging_performed(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item


@router.post("/{test_order_id}/culture-stage", response_model=TechnicianWorklistItemResponse, summary="Record culture multi-stage transition (Section 5.5)")
def culture_stage(
    test_order_id: int,
    data: CultureStageRequest,
    actor: CurrentActor = Depends(require_permission("worklist.update")),
    db: Session = Depends(get_db),
):
    """
    Transitions culture test through multi-day stages: INCUBATING, PRELIMINARY, FINAL.
    """
    item = record_culture_stage(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item


@router.post("/{test_order_id}/outsourced", response_model=TechnicianWorklistItemResponse, summary="Record outside laboratory dispatch or receipt (Section 5.5)")
def outsourced_stage(
    test_order_id: int,
    data: OutsourcedStageRequest,
    actor: CurrentActor = Depends(require_permission("worklist.update")),
    db: Session = Depends(get_db),
):
    """
    Records external referral laboratory dispatch (SENT) or specimen receipt (RECEIVED).
    """
    item = record_outsourced_stage(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item


@router.get("/{test_order_id}/events", response_model=List[TestOrderEventResponse], summary="Get append-only operational lifecycle history")
def list_events(
    test_order_id: int,
    actor: CurrentActor = Depends(require_permission("worklist.view")),
    db: Session = Depends(get_db),
):
    """
    Retrieves full timestamped lifecycle event history for a laboratory order.
    """
    return get_order_events(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
    )


@router.get("/{test_order_id}/barcode", response_model=BarcodeLabelResponse, summary="Get printable barcode label data and vector SVG")
def get_barcode(
    test_order_id: int,
    actor: CurrentActor = Depends(require_permission("worklist.view")),
    db: Session = Depends(get_db),
):
    """
    Generates Code 128 vector SVG barcode label payload for specimen tubes (50mm x 25mm / 50mm x 30mm).
    Strictly financial-free.
    """
    return generate_barcode_label_data(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
    )


@router.post("/{test_order_id}/status", response_model=TechnicianWorklistItemResponse, summary="Update task workflow status")
def change_status(
    test_order_id: int,
    data: UpdateOrderStatusRequest,
    actor: CurrentActor = Depends(require_permission("worklist.update")),
    db: Session = Depends(get_db),
):
    """
    Transitions laboratory order status. Enforces Prompt 06 transition rules:
    - Pre-sample tasks cannot transition to COMPLETED.
    - Doctor-required tests require physician authorization.
    - Rejected/spoiled tasks follow Not Performed workflow.
    """
    item = update_order_status(
        db=db,
        tenant_id=actor.tenant_id,
        test_order_id=test_order_id,
        actor=actor,
        data=data,
    )
    db.commit()
    return item

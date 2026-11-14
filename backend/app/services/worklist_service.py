import re
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc, or_, and_, func
from sqlalchemy.orm import Session
from backend.app.core.permissions import has_permission, is_money_restricted
from backend.app.core.samples import (
    SAMPLE_REQUIRED_COMPLETE_MESSAGE,
    SAMPLE_REQUIRED_STAGE_MESSAGE,
    imaging_sql_clause,
    is_imaging_test,
    requires_sample,
    sample_gate_blocks,
)
from backend.app.core.timezone import utc_now
from backend.app.core.security import CurrentActor
from backend.app.models.test_order import TestOrder, AssignmentHistory, TestOrderEvent
from backend.app.models.invoice import InvoiceLine, Invoice
from backend.app.models.patient import Patient
from backend.app.models.test import Test
from backend.app.models.sample import Sample
from backend.app.models.user import Staff
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
)
from backend.app.services.audit_service import log_audit_event
from backend.app.services.stock_boundary_service import trigger_specimen_stock_deduction
from backend.app.services.barcode_service import generate_code128_svg
from backend.app.core.lab_sections import lab_section_label
from backend.app.models.result import Result
from backend.app.services.line_lock_service import lock_line_at_result_completion
from backend.app.services.routing_service import ensure_order_access, record_actor, visibility_clause
from backend.app.services.ready_report_service import ready_clause, ready_order_ids


def format_elapsed_time(mins: int) -> str:
    """Helper formatting elapsed minutes into readable duration string."""
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    rem = mins % 60
    if rem > 0:
        return f"{hours}h {rem}m"
    return f"{hours}h"


def build_worklist_item(order: TestOrder, ready: Optional[bool] = None) -> TechnicianWorklistItemResponse:
    """
    Constructs a strictly financial-free operational task item
    enforcing Section 5.4 strict financial-data separation.
    `ready`: precomputed Ready flag (batch, from the shared ready_clause); computed when None.
    """
    now_ts = utc_now()
    inv = order.invoice_line.invoice
    patient = inv.patient
    test = order.invoice_line.test
    sample = order.sample

    # 1. Patient clock: elapsed time since invoice confirmation
    patient_elapsed_mins = max(0, int((now_ts - inv.created_at).total_seconds() / 60))
    patient_elapsed_str = format_elapsed_time(patient_elapsed_mins)

    # 2. Lab clock: elapsed time since sample collection
    lab_elapsed_mins = None
    lab_elapsed_str = None
    sample_status = "PENDING"
    if sample and sample.collected_at:
        sample_status = sample.status
        lab_elapsed_mins = max(0, int((now_ts - sample.collected_at).total_seconds() / 60))
        lab_elapsed_str = format_elapsed_time(lab_elapsed_mins)
    elif sample and sample.status in ("REJECTED", "SPOILED"):
        sample_status = sample.status

    # 3. Turnaround time & Late indicator evaluation (Section 4.6)
    tat_hours = order.turnaround_hours or (test.turnaround_hours if test else None)
    tat_mins = (tat_hours * 60) if tat_hours else None
    tat_display = f"{tat_hours}h" if tat_hours else "Not Configured"

    is_late = False
    late_reason = None
    if tat_mins is not None and order.status not in ("COMPLETED", "CANCELLED", "REJECTED", "SPOILED"):
        if patient_elapsed_mins > tat_mins:
            is_late = True
            late_reason = f"Patient clock ({patient_elapsed_str}) exceeded TAT ({tat_display})"
        elif lab_elapsed_mins is not None and lab_elapsed_mins > tat_mins:
            is_late = True
            late_reason = f"Lab clock ({lab_elapsed_str}) exceeded TAT ({tat_display})"

    # Age display
    age_str = f"{inv.visit.age_value} {inv.visit.age_unit}" if inv.visit else None

    # Line lock check
    is_line_locked = getattr(order.invoice_line, "is_locked", False) or (
        sample is not None and sample.status == "COLLECTED"
    )

    # Result state
    has_res = bool(getattr(order, "result", None) is not None)
    res_status = order.result.status if has_res else None
    # Prompt 10F (F3): "Ready" comes from the one shared definition (ready_report_service.ready_clause):
    # ENTERED result, order not cancelled / not performed / awaiting doctor. Completion not required.
    if ready is None:
        sess = Session.object_session(order)
        ready = bool(sess is not None and has_res and order.id in ready_order_ids(sess, [order.id]))
    report_ready = bool(ready)

    # D15 Refund request check for this line
    d15_status = None
    line_id = order.invoice_line_id
    if line_id:
        from backend.app.models.refund import RefundRequest
        active_req = (
            Session.object_session(order)
            .execute(
                select(RefundRequest)
                .where(
                    RefundRequest.invoice_line_id == line_id,
                )
                .order_by(desc(RefundRequest.requested_at))
            )
            .scalars()
            .first()
            if Session.object_session(order)
            else None
        )
        if active_req:
            d15_status = active_req.status

    return TechnicianWorklistItemResponse(
        test_order_id=order.id,
        invoice_id=inv.id,
        invoice_no=inv.invoice_no,
        status=order.status,
        urgent=order.urgent,
        patient_id=patient.id,
        patient_name=patient.name,
        patient_code=patient.patient_code,
        patient_gender=patient.gender,
        patient_age=age_str,
        patient_phone=patient.phone,
        test_id=test.id if test else order.invoice_line.test_id,
        test_code=order.invoice_line.test_code_snapshot,
        test_name=order.invoice_line.test_name_snapshot,
        department=order.department or order.invoice_line.department_snapshot,
        sample_type=test.sample_type if test else None,
        sample_route=order.sample_route,
        report_template=test.report_template if test else "NUMERIC_TABLE",
        approval_rule=test.approval_rule if test else "TECHNICIAN_FINAL",
        requires_doctor=test.requires_doctor if test else (order.performing_role == "DOCTOR"),
        sample_id=sample.id if sample else None,
        sample_code=sample.sample_code if sample else None,
        temp_sample_id=sample.temp_sample_id if sample else None,
        sample_status=sample_status,
        sample_collected_at=sample.collected_at if sample else None,
        is_line_locked=is_line_locked,
        rejection_reason=sample.rejection_reason if sample else None,
        outcome=getattr(order, "outcome", None),
        result_status=res_status,
        has_result=has_res,
        patient_followup_required=order.patient_followup_required,
        patient_contact_status=order.patient_contact_status,
        patient_contact_notes=order.patient_contact_notes,
        d15_refund_status=d15_status,
        culture_stage=order.culture_stage,
        outsourced_status=order.outsourced_status,
        outsourced_lab_name=order.outsourced_lab_name,
        outsourced_sent_at=order.outsourced_sent_at,
        outsourced_received_at=order.outsourced_received_at,
        outsourced_ref_no=order.outsourced_ref_no,
        assigned_to_id=order.assigned_to_id,
        assigned_to_name=order.assigned_to.display_name if order.assigned_to else None,
        assigned_destination=order.assigned_destination,
        assigned_at=order.assigned_at,
        turnaround_hours=tat_hours,
        tat_display=tat_display,
        ordered_at=inv.created_at,
        patient_clock_elapsed_mins=patient_elapsed_mins,
        patient_clock_display=patient_elapsed_str,
        lab_clock_elapsed_mins=lab_elapsed_mins,
        lab_clock_display=lab_elapsed_str,
        is_late=is_late,
        late_reason=late_reason,
        requires_sample=requires_sample(test, order),
        is_imaging=is_imaging_test(test, order),
        lab_section=order.lab_section,
        lab_section_label=lab_section_label(order.lab_section),
        report_ready=report_ready,
    )


def _worklist_base_stmt(db: Session, tenant_id: str, actor: CurrentActor, staff_id: Optional[int] = None):
    """Orders the actor may see on the worklist (used by the list and by the summary counts)."""
    stmt = (
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .join(InvoiceLine.invoice)
        .join(Invoice.patient)
        .where(
            TestOrder.tenant_id == tenant_id,
            InvoiceLine.status != "CANCELLED",
        )
    )

    # Worklist Access Boundary (Prompt 10E Part 7): room based.
    # - worklist.view_all (Admin/Owner): every order; staff_id inspects that technician's room.
    # - LAB_TECH: every order whose room equals their own lab_section (assigned_to_id not needed).
    # - DOCTOR (worklist.doctor_queue): AWAITING_DOCTOR orders from all rooms (+ completed doctor-routed).
    if has_permission(actor, "worklist.view_all"):
        if staff_id:
            inspected = db.get(Staff, staff_id)
            stmt = stmt.where(TestOrder.lab_section == (inspected.lab_section if inspected else None))
    else:
        clause = visibility_clause(actor)
        if clause is not None:
            stmt = stmt.where(clause)
    return stmt


def get_technician_worklist(
    db: Session,
    tenant_id: str,
    actor: CurrentActor,
    staff_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    department_filter: Optional[str] = None,
    urgent_only: bool = False,
    query: Optional[str] = None,
    limit: int = 100,
) -> List[TechnicianWorklistItemResponse]:
    """
    Retrieves the operational worklist for a laboratory technician or supervisor.
    Enforces worklist access boundaries (Section 5.5):
    - A technician sees their own assigned tasks only.
    - Admin/Owner can optionally inspect by staff_id or view all tasks.
    """
    stmt = _worklist_base_stmt(db, tenant_id, actor, staff_id)

    # Status filter
    if status_filter and status_filter.strip() not in ("ALL", ""):
        norm = status_filter.strip().upper()
        if norm == "SAMPLE_PENDING":
            stmt = stmt.outerjoin(TestOrder.sample).where(
                or_(Sample.id.is_(None), Sample.status == "PENDING"),
                TestOrder.status.not_in(["COMPLETED", "CANCELLED", "REJECTED", "SPOILED"]),
            )
        elif norm == "REJECTED":
            stmt = stmt.where(TestOrder.status.in_(["REJECTED", "SPOILED"]))
        elif norm == "CULTURE":
            stmt = stmt.join(InvoiceLine.test).where(Test.report_template == "CULTURE_SENSITIVITY")
        elif norm == "IMAGING":
            # Prompt 10F: the same imaging definition as core/samples.py (single source)
            stmt = stmt.join(InvoiceLine.test).where(imaging_sql_clause(Test))
        elif norm == "OUTSOURCED":
            stmt = stmt.join(InvoiceLine.test).where(Test.is_outsourced == True)
        elif norm == "READY":
            # Prompt 10F (F3): the one shared Ready definition (tile count, this list, /reports/ready)
            stmt = stmt.where(ready_clause())
        elif norm == "LATE":
            pass  # evaluated after loading (late depends on the TAT clocks)
        elif norm == "UNASSIGNED_ROOM":
            stmt = stmt.where(TestOrder.status == "UNASSIGNED")
        else:
            stmt = stmt.where(TestOrder.status == norm)

    # Department filter
    if department_filter and department_filter.strip() not in ("ALL", ""):
        stmt = stmt.where(
            or_(
                TestOrder.department == department_filter.strip(),
                InvoiceLine.department_snapshot == department_filter.strip(),
            )
        )

    # Urgent STAT filter
    if urgent_only:
        stmt = stmt.where(TestOrder.urgent == True)

    # Barcode / Search Query (Section 5.6)
    if query and query.strip():
        q = query.strip()
        stmt = stmt.outerjoin(TestOrder.sample).where(
            or_(
                Patient.name.ilike(f"%{q}%"),
                Patient.patient_code.ilike(f"%{q}%"),
                Invoice.invoice_no.ilike(f"%{q}%"),
                InvoiceLine.test_name_snapshot.ilike(f"%{q}%"),
                InvoiceLine.test_code_snapshot.ilike(f"%{q}%"),
                Sample.sample_code.ilike(f"%{q}%"),
                Sample.temp_sample_id.ilike(f"%{q}%"),
            )
        )

    # Order by Urgent STAT first, then creation timestamp
    stmt = stmt.order_by(desc(TestOrder.urgent), desc(TestOrder.created_at)).limit(limit)

    orders = list(db.execute(stmt).scalars().all())
    ready_ids = ready_order_ids(db, [o.id for o in orders])
    items = [build_worklist_item(o, ready=o.id in ready_ids) for o in orders]
    if status_filter and status_filter.strip().upper() == "LATE":
        items = [i for i in items if i.is_late]
    return items


def record_sample_taken(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: SampleTakenRequest,
) -> TechnicianWorklistItemResponse:
    """
    Executes specimen collection action (Prompt 06 Module 12).
    - Records Sample Taken event in samples table.
    - Locks corresponding invoice line against ordinary cancellation/refund.
    - Triggers stock deduction integration boundary (deferred to Module 16).
    - Records append-only TestOrderEvent with timestamp and actor attribution.
    - Sets order status to IN_PROGRESS.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order, "You can only record samples for orders in your room.")

    if order.status in ("COMPLETED", "CANCELLED", "REJECTED", "SPOILED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot collect specimen for order in '{order.status}' status.",
        )

    now_ts = utc_now()
    collection_time = data.collected_at or now_ts

    # Audit manual time adjustment (>5m drift)
    if data.collected_at:
        drift_secs = abs((data.collected_at - now_ts).total_seconds())
        if drift_secs > 300:
            log_audit_event(
                db=db,
                tenant_id=tenant_id,
                action="SAMPLE_TIME_MANUAL_EDIT",
                entity_type="TEST_ORDER",
                entity_id=order.id,
                acting_role=actor.role,
                actor_id=actor.id,
                before_value=now_ts.isoformat(),
                after_value=data.collected_at.isoformat(),
            )

    sample = order.sample
    if sample:
        sample.status = "COLLECTED"
        sample.collected_at = collection_time
        sample.collected_by_id = actor.id
        if data.sample_type:
            sample.sample_type = data.sample_type
        if data.temp_sample_id:
            sample.temp_sample_id = data.temp_sample_id
    else:
        inv_no = order.invoice_line.invoice.invoice_no
        sample_code = f"SMP-{inv_no}-{order.id}"
        sample_type = data.sample_type or (
            order.invoice_line.test.sample_type if order.invoice_line.test else "Specimen"
        )
        sample = Sample(
            tenant_id=tenant_id,
            test_order_id=order.id,
            sample_code=sample_code,
            temp_sample_id=data.temp_sample_id,
            sample_type=sample_type,
            status="COLLECTED",
            collected_at=collection_time,
            collected_by_id=actor.id,
        )
        db.add(sample)

    # 1. Module 12 Line Lock: Lock invoice line against ordinary cancellation/refund
    order.invoice_line.is_locked = True
    order.invoice_line.locked_at = collection_time
    order.invoice_line.locked_reason = f"Specimen collected ({sample.sample_code})"

    # 2. Module 12 Stock Boundary: Trigger reagent stock consumption boundary
    trigger_specimen_stock_deduction(db=db, tenant_id=tenant_id, test_order=order, actor=actor)

    # 3. Transition order status to IN_PROGRESS if pending
    if order.status in ("ASSIGNED", "PENDING", "SAMPLE_PENDING", "UNASSIGNED"):
        order.status = "IN_PROGRESS"
    record_actor(order, actor)  # who acted (not used for visibility)

    # 4. Append operational lifecycle event
    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type="SAMPLE_COLLECTED",
        stage="COLLECTED",
        description=f"Specimen collected ({sample.sample_type or 'Specimen'}) with Barcode {sample.sample_code}",
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=collection_time,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="SAMPLE_TAKEN",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"Sample Code: {sample.sample_code}, Time: {collection_time.isoformat()}, Line Locked: True",
    )

    db.flush()
    return build_worklist_item(order)


def record_sample_rejected(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: RejectSampleRequest,
) -> TechnicianWorklistItemResponse:
    """
    Executes controlled spoiled or rejected specimen workflow (Prompt 06 Section 5.3 & D15 rule).
    - Requires mandatory rejection reason.
    - Flags order and sample as REJECTED or SPOILED.
    - Flags patient for contact follow-up.
    - Preserves invoice line lock (D15 rule: Not Performed exception, no free recollection on same line).
    - Records append-only TestOrderEvent and audit log.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order, "You can only reject specimens for orders in your room.")

    if not data.rejection_reason or len(data.rejection_reason.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A specific rejection reason is mandatory.",
        )

    now_ts = utc_now()
    spoil_status = data.spoil_type.strip().upper()
    if spoil_status not in ("REJECTED", "SPOILED"):
        spoil_status = "REJECTED"

    sample = order.sample
    if sample:
        sample.status = spoil_status
        sample.rejected_at = now_ts
        sample.rejected_by_id = actor.id
        sample.rejection_reason = data.rejection_reason.strip()
        sample.rejection_notes = data.notes.strip() if data.notes else None

    prev_status = order.status
    order.status = spoil_status
    order.outcome = "NOT_PERFORMED"  # Module 12 / D15 invariant: Not Performed outcome
    order.patient_followup_required = True
    order.patient_contact_status = "PENDING_CALL"

    # Line remains locked under D15 rule; cancellation requires Admin/Owner exception
    order.invoice_line.is_locked = True
    order.invoice_line.locked_reason = f"Specimen {spoil_status}: {data.rejection_reason.strip()} (D15 rule locked)"

    # Append operational event
    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type=f"SAMPLE_{spoil_status}",
        stage=spoil_status,
        description=f"Specimen marked {spoil_status}. Reason: {data.rejection_reason.strip()}",
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=f"SAMPLE_{spoil_status}",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        before_value=prev_status,
        after_value=f"Reason: {data.rejection_reason.strip()} | Patient Follow-up: PENDING_CALL",
    )

    db.flush()
    return build_worklist_item(order)


def record_patient_contact(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: PatientContactRequest,
) -> TechnicianWorklistItemResponse:
    """
    Records patient call follow-up outcome for spoiled/rejected specimens (Section 5.3 & D15 rule).
    Enforces that new recollection requires a new bill line; no free re-runs.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order)

    contact_status = data.contact_status.strip().upper()
    valid_statuses = ("CALLED", "RECOLLECTION_AGREED", "REFUND_REQUESTED")
    if contact_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid contact status. Must be one of: {', '.join(valid_statuses)}",
        )

    now_ts = utc_now()
    order.patient_contact_status = contact_status
    order.patient_contacted_at = now_ts
    order.patient_contact_notes = data.notes.strip() if data.notes else None
    if contact_status in ("CALLED", "RECOLLECTION_AGREED", "REFUND_REQUESTED"):
        order.patient_followup_required = False

    desc_text = f"Patient Contacted: {contact_status}"
    if contact_status == "RECOLLECTION_AGREED":
        desc_text += " (Patient agreed to recollection. Requires new bill line and sample ID)."
    elif contact_status == "REFUND_REQUESTED":
        desc_text += " (Patient requested refund. D15 Refund Request submitted for Admin/Owner approval)."
        # FIX 4: Automatically submit the D15 Refund Request into PENDING_ADMIN_APPROVAL state
        from backend.app.services.refund_service import initiate_d15_refund_request
        try:
            initiate_d15_refund_request(
                db=db,
                tenant_id=tenant_id,
                test_order_id=order.id,
                requested_by_id=actor.id,
                notes=data.notes,
                acting_role=actor.role,
            )
        except Exception as e:
            # If already pending, proceed safely without blocking contact record
            pass

    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type="PATIENT_CONTACTED",
        stage=contact_status,
        description=desc_text,
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="PATIENT_CONTACTED",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"Status: {contact_status} | Notes: {data.notes or 'None'}",
    )

    db.flush()
    return build_worklist_item(order)


def record_imaging_performed(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: ImagingPerformedRequest,
) -> TechnicianWorklistItemResponse:
    """
    Executes imaging examination performed milestone (Section 5.5).
    - Prompt 12: does NOT lock the line any more; the line locks at result completion (line_lock_service).
    - Moves task to AWAITING_DOCTOR queue for visiting physician interpretation.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order)

    test = order.invoice_line.test
    if not is_imaging_test(test, order):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This action is only applicable to Radiology and Imaging investigations.",
        )

    now_ts = utc_now()
    perf_time = data.performed_at or now_ts
    order.status = "AWAITING_DOCTOR"

    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type="IMAGING_PERFORMED",
        stage="PERFORMED",
        description="Imaging scan performed. Order routed to visiting doctor queue.",
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=perf_time,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="IMAGING_PERFORMED",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value="Scan Performed. Routed to Doctor Queue. Line not locked (locks at result completion).",
    )

    db.flush()
    return build_worklist_item(order)


def record_culture_stage(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: CultureStageRequest,
) -> TechnicianWorklistItemResponse:
    """
    Executes culture multi-stage lifecycle transition (Section 5.5).
    Stages: INCUBATING, PRELIMINARY, FINAL.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order)

    target_stage = data.stage.strip().upper()
    valid_stages = ("INCUBATING", "PRELIMINARY", "FINAL")
    if target_stage not in valid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid culture stage '{target_stage}'. Must be one of: {', '.join(valid_stages)}",
        )

    # Prompt 10F (F4): a culture cannot progress before its specimen is collected
    if sample_gate_blocks(order.invoice_line.test, order):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=SAMPLE_REQUIRED_STAGE_MESSAGE)

    now_ts = utc_now()
    order.culture_stage = target_stage

    # Fix 3 (D19, M12): Culture stage progression does NOT auto-complete the TestOrder.
    # Culture stage and TestOrder status are independent lifecycles.
    if order.status not in ("COMPLETED", "CANCELLED", "REJECTED", "SPOILED"):
        order.status = "IN_PROGRESS"

    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type=f"CULTURE_{target_stage}",
        stage=target_stage,
        description=f"Culture examination moved to {target_stage} stage.",
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=f"CULTURE_{target_stage}",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"Culture stage: {target_stage} | Notes: {data.notes or 'None'}",
    )

    db.flush()
    # Module 14 (Prompt 16): a doctor approval given while the culture was still running finalizes the
    # report now that the stage is FINAL (technician-final cultures need the explicit Finalize click).
    if target_stage == "FINAL":
        from backend.app.services.report_finalization_service import try_auto_finalize
        try_auto_finalize(db, actor, order)
    return build_worklist_item(order)


def record_outsourced_stage(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: OutsourcedStageRequest,
) -> TechnicianWorklistItemResponse:
    """
    Executes outside referral laboratory dispatch or receipt (Section 5.5).
    Action: SENT or RECEIVED.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order)

    action = data.action.strip().upper()
    now_ts = data.timestamp or utc_now()

    if action == "SENT" and sample_gate_blocks(order.invoice_line.test, order):
        # Prompt 10F (F4): a specimen cannot be dispatched before it is collected
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=SAMPLE_REQUIRED_STAGE_MESSAGE)

    if action == "SENT":
        order.outsourced_status = "SENT"
        order.outsourced_sent_at = now_ts
        if data.lab_name:
            order.outsourced_lab_name = data.lab_name.strip()
        if data.ref_no:
            order.outsourced_ref_no = data.ref_no.strip()
        order.status = "IN_PROGRESS"
        desc = f"Specimen dispatched to outside laboratory: {order.outsourced_lab_name or 'Referral Lab'}"
    elif action == "RECEIVED":
        order.outsourced_status = "RECEIVED"
        order.outsourced_received_at = now_ts
        if data.ref_no:
            order.outsourced_ref_no = data.ref_no.strip()
        order.status = "IN_PROGRESS"
        desc = f"Results / specimen received back from outside laboratory (Ref: {order.outsourced_ref_no or 'N/A'})"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action must be SENT or RECEIVED.")

    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type=f"OUTSOURCED_{action}",
        stage=action,
        description=desc,
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action=f"OUTSOURCED_{action}",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        after_value=f"{action} | Lab: {order.outsourced_lab_name} | Ref: {order.outsourced_ref_no}",
    )

    db.flush()
    return build_worklist_item(order)


def _sanitize_tech_event_text(text: Optional[str]) -> Optional[str]:
    """Sanitizes monetary figures from historical lifecycle descriptions for Lab Techs (Fix 5)."""
    if not text:
        return text
    cleaned = re.sub(r'(?:Tk\.?|৳)\s*\d+(?:\.\d+)?', '[REDACTED]', text)
    cleaned = re.sub(r'for\s+\[REDACTED\]\s*', '', cleaned)
    cleaned = re.sub(r':\s*\[REDACTED\]', '', cleaned)
    return cleaned.strip()


def get_order_events(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
) -> List[TestOrderEventResponse]:
    """Retrieves full append-only operational lifecycle history for an order."""
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order, "Access denied.")

    stmt = (
        select(TestOrderEvent)
        .where(TestOrderEvent.test_order_id == test_order_id, TestOrderEvent.tenant_id == tenant_id)
        .order_by(TestOrderEvent.created_at.asc())
    )
    events = list(db.execute(stmt).scalars().all())

    is_tech = is_money_restricted(actor)  # absolute, role based (never overridable)
    return [
        TestOrderEventResponse(
            id=ev.id,
            test_order_id=ev.test_order_id,
            event_type=ev.event_type,
            stage=ev.stage,
            description=_sanitize_tech_event_text(ev.description) if is_tech else ev.description,
            notes=_sanitize_tech_event_text(ev.notes) if is_tech else ev.notes,
            actor_id=ev.actor_id,
            actor_name=ev.actor_name,
            actor_role=ev.actor_role,
            created_at=ev.created_at,
        )
        for ev in events
    ]


def generate_barcode_label_data(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
) -> BarcodeLabelResponse:
    """Generates printable barcode label metadata and vector SVG for a specimen."""
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order, "Access denied.")

    sample = order.sample
    if not sample or not sample.sample_code:
        # Create a pending sample code if not yet initialized
        inv_no = order.invoice_line.invoice.invoice_no
        sample_code = f"SMP-{inv_no}-{order.id}"
    else:
        sample_code = sample.sample_code

    patient = order.invoice_line.invoice.patient
    visit = order.invoice_line.invoice.visit
    test = order.invoice_line.test
    age_str = f"{visit.age_value} {visit.age_unit}" if visit else None

    # Generate pure vector SVG barcode
    svg = generate_code128_svg(
        data=sample_code,
        module_width=1.4,
        height=38.0,
        include_text=True,
    )

    return BarcodeLabelResponse(
        test_order_id=order.id,
        sample_code=sample_code,
        temp_sample_id=sample.temp_sample_id if sample else None,
        patient_name=patient.name,
        patient_code=patient.patient_code,
        patient_gender=patient.gender,
        patient_age=age_str,
        test_code=order.invoice_line.test_code_snapshot,
        test_name=order.invoice_line.test_name_snapshot,
        department=order.department or order.invoice_line.department_snapshot,
        sample_type=sample.sample_type if sample else (test.sample_type if test else "Specimen"),
        collected_at=sample.collected_at if sample else None,
        barcode_svg=svg,
        barcode_format="CODE128",
    )


def update_order_status(
    db: Session,
    tenant_id: str,
    test_order_id: int,
    actor: CurrentActor,
    data: UpdateOrderStatusRequest,
) -> TechnicianWorklistItemResponse:
    """
    Updates the laboratory workflow state of a test order with strict transition rules.
    Prompt 06 Worklist Fix:
    - Before Sample Taken, a sample-based task must not transition to COMPLETED.
    - Doctor-required tests cannot be completed directly by LAB_TECH.
    - Rejected/spoiled tasks cannot be completed.
    """
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")

    ensure_order_access(actor, order, "You can only update status for orders in your room.")

    target_status = data.status.strip().upper()
    valid_statuses = ("IN_PROGRESS", "AWAITING_DOCTOR", "COMPLETED", "SAMPLE_PENDING", "CANCELLED")
    if target_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{target_status}'. Must be one of: {', '.join(valid_statuses)}",
        )

    test = order.invoice_line.test
    needs_sample = requires_sample(test, order)  # Prompt 10E: single helper
    requires_doctor = (test and test.requires_doctor) or (order.performing_role == "DOCTOR")

    # Business Transition Invariants (Prompt 06 Section 6):
    if target_status == "COMPLETED":
        # 1. Sample collection invariant
        if needs_sample and (not order.sample or order.sample.status != "COLLECTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=SAMPLE_REQUIRED_COMPLETE_MESSAGE,
            )

        # 2. Doctor routing invariant
        if requires_doctor and not has_permission(actor, "result.complete_doctor_routed"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Visiting physician or radiologist authorization required. Technician cannot complete doctor-routed test directly.",
            )

        # 3. Rejected sample invariant
        if order.status in ("REJECTED", "SPOILED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete a {order.status} test order. Follows Not Performed exception workflow.",
            )

        # 4. Culture stage completion guard (Fix 3: D19, M12)
        is_culture = (test and test.report_template == "CULTURE_SENSITIVITY") or (order.culture_stage is not None)
        if is_culture and order.culture_stage != "FINAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Culture test cannot be completed while in '{order.culture_stage or 'INCUBATING'}' stage. Culture stage must reach FINAL before completion.",
            )

    prev_status = order.status
    order.status = target_status
    now_ts = utc_now()
    if target_status == "COMPLETED":
        lock_line_at_result_completion(order, now_ts)  # Prompt 12: no-sample tests lock at result completion

    # Append operational event
    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type="STATUS_CHANGED",
        stage=target_status,
        description=f"Task moved from {prev_status} to {target_status}. Notes: {data.notes or 'Routine transition'}",
        notes=data.notes,
        actor_id=actor.id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        created_at=now_ts,
    )
    db.add(lifecycle_event)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="UPDATE_ORDER_STATUS",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=actor.role,
        actor_id=actor.id,
        before_value=prev_status,
        after_value=f"{target_status} ({data.notes or 'Routine transition'})",
    )

    db.flush()
    return build_worklist_item(order)


def get_worklist_summary(
    db: Session,
    tenant_id: str,
    actor: CurrentActor,
    staff_id: Optional[int] = None,
) -> WorklistSummaryResponse:
    """Returns aggregated KPI summary tiles for the technician workbench."""
    # Prompt 10E: same room-based visibility as the list (Admin/Owner: all rooms, or the room of
    # the inspected staff_id). Before 10E an Admin's summary counted only orders assigned to them.
    inspect_id = staff_id if (staff_id and has_permission(actor, "worklist.view_all")) else None
    target_staff_id = inspect_id or actor.id
    staff = db.get(Staff, target_staff_id)
    tech_name = staff.display_name if staff else actor.display_name
    section = staff.lab_section if staff else getattr(actor, "lab_section", None)
    dept = lab_section_label(section) or (staff.department if staff else None)

    items = get_technician_worklist(
        db=db,
        tenant_id=tenant_id,
        actor=actor,
        staff_id=inspect_id,
        limit=1000,
    )

    total_assigned = len(items)
    urgent_count = sum(1 for i in items if i.urgent and i.status != "COMPLETED")
    sample_pending_count = sum(1 for i in items if i.sample_status == "PENDING" and i.status not in ("COMPLETED", "CANCELLED", "REJECTED", "SPOILED"))
    in_progress_count = sum(1 for i in items if i.status == "IN_PROGRESS")
    awaiting_doctor_count = sum(1 for i in items if i.status == "AWAITING_DOCTOR")
    late_count = sum(1 for i in items if i.is_late)
    completed_count = sum(1 for i in items if i.status == "COMPLETED")
    rejected_count = sum(1 for i in items if i.status in ("REJECTED", "SPOILED"))
    culture_count = sum(1 for i in items if i.report_template == "CULTURE_SENSITIVITY")
    imaging_count = sum(1 for i in items if i.is_imaging)
    outsourced_count = sum(1 for i in items if i.outsourced_status is not None)
    # Prompt 10F (F3): counted in SQL with the same visibility and the same ready_clause as the list
    ready_count = db.execute(
        select(func.count()).select_from(
            _worklist_base_stmt(db, tenant_id, actor, inspect_id).where(ready_clause()).subquery()
        )
    ).scalar_one()
    unassigned_count = sum(1 for i in items if i.status == "UNASSIGNED")

    return WorklistSummaryResponse(
        technician_id=target_staff_id,
        technician_name=tech_name,
        department=dept,
        total_assigned=total_assigned,
        urgent_count=urgent_count,
        sample_pending_count=sample_pending_count,
        in_progress_count=in_progress_count,
        awaiting_doctor_count=awaiting_doctor_count,
        late_count=late_count,
        completed_count=completed_count,
        rejected_count=rejected_count,
        culture_count=culture_count,
        imaging_count=imaging_count,
        outsourced_count=outsourced_count,
        ready_count=ready_count,
        unassigned_count=unassigned_count,
        lab_section=section,
    )

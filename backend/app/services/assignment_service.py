from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.models.test_order import TestOrder, AssignmentHistory, TestOrderEvent
from backend.app.models.invoice import InvoiceLine, Invoice
from backend.app.models.patient import Patient
from backend.app.schemas.assignment import AssignedTestOrderResponse, UnassignedOrderResponse, ManualAssignRequest
from backend.app.services.audit_service import log_audit_event
from backend.app.core.lab_sections import lab_section_label
from backend.app.services.routing_service import move_order_to_room, reassign_block_reason, resolve_room


def list_unassigned_test_orders(
    db: Session,
    tenant_id: str,
    department: Optional[str] = None,
    limit: int = 50,
) -> List[UnassignedOrderResponse]:
    """Lists test orders that are in the explicit UNASSIGNED state."""
    stmt = (
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .join(InvoiceLine.invoice)
        .join(Invoice.patient)
        .where(
            TestOrder.tenant_id == tenant_id,
            TestOrder.status == "UNASSIGNED",
            InvoiceLine.status != "CANCELLED",
        )
        .order_by(desc(InvoiceLine.created_at))
    )

    if department and department.strip() != "ALL":
        stmt = stmt.where(InvoiceLine.department_snapshot == department.strip())

    orders = list(db.execute(stmt.limit(limit)).scalars().all())
    return [
        UnassignedOrderResponse(
            test_order_id=o.id,
            invoice_id=o.invoice_line.invoice.id,
            invoice_no=o.invoice_line.invoice.invoice_no,
            patient_id=o.invoice_line.invoice.patient.id,
            patient_name=o.invoice_line.invoice.patient.name,
            patient_code=o.invoice_line.invoice.patient.patient_code,
            patient_phone=o.invoice_line.invoice.patient.phone,
            test_code=o.invoice_line.test_code_snapshot,
            test_name=o.invoice_line.test_name_snapshot,
            department=o.invoice_line.department_snapshot,
            urgent=o.invoice_line.urgent,
            status=o.status,
            created_at=o.invoice_line.created_at,
            lab_section=o.lab_section,
            lab_section_label=lab_section_label(o.lab_section),
        )
        for o in orders
    ]


ASSIGNED_VIEW_STATUS_FILTERS = (
    "ALL", "OPEN", "UNASSIGNED", "ASSIGNED", "SAMPLE_PENDING", "IN_PROGRESS", "AWAITING_DOCTOR",
    "PENDING", "COMPLETED", "CANCELLED", "NOT_PERFORMED",
)


def list_assigned_test_orders(
    db: Session,
    tenant_id: str,
    actor,
    status_filter: Optional[str] = None,
    lab_section: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 200,
) -> List[AssignedTestOrderResponse]:
    """Prompt 10F (F1): every test order with its room and the room's active technicians (or the
    explicit UNASSIGNED state). Money-free. can_reassign is decided by the permission layer
    (worklist.reassign) and the one reassignability rule (routing_service.reassign_block_reason)."""
    from sqlalchemy import or_
    from backend.app.core.permissions import has_permission
    from backend.app.models.user import Staff

    stmt = (
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .join(InvoiceLine.invoice)
        .join(Invoice.patient)
        .where(TestOrder.tenant_id == tenant_id)
    )
    norm = (status_filter or "ALL").strip().upper()
    if norm not in ASSIGNED_VIEW_STATUS_FILTERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unknown status filter '{status_filter}'. Use one of: {', '.join(ASSIGNED_VIEW_STATUS_FILTERS)}.")
    line_cancelled = or_(InvoiceLine.status == "CANCELLED", TestOrder.status == "CANCELLED")
    if norm == "CANCELLED":
        stmt = stmt.where(line_cancelled)
    elif norm == "NOT_PERFORMED":
        stmt = stmt.where(~line_cancelled, or_(TestOrder.status.in_(("REJECTED", "SPOILED")), TestOrder.outcome == "NOT_PERFORMED"))
    elif norm == "OPEN":
        stmt = stmt.where(~line_cancelled, TestOrder.status.not_in(("COMPLETED", "REJECTED", "SPOILED")))
    elif norm != "ALL":
        stmt = stmt.where(~line_cancelled, TestOrder.status == norm)
    if lab_section and lab_section.strip().upper() not in ("", "ALL"):
        sec = lab_section.strip().upper()
        stmt = stmt.where(TestOrder.lab_section.is_(None) if sec == "NONE" else TestOrder.lab_section == sec)
    if query and query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(or_(
            Patient.name.ilike(q), Patient.patient_code.ilike(q), Invoice.invoice_no.ilike(q),
            InvoiceLine.test_name_snapshot.ilike(q), InvoiceLine.test_code_snapshot.ilike(q),
        ))
    orders = list(db.execute(stmt.order_by(desc(TestOrder.created_at), desc(TestOrder.id)).limit(limit)).scalars().all())

    # Active technicians per room (one query)
    techs: dict = {}
    for s in db.execute(
        select(Staff).where(Staff.tenant_id == tenant_id, Staff.active == True, Staff.deleted_at.is_(None), Staff.role == "LAB_TECH")  # noqa: E712
        .order_by(Staff.display_name)
    ).scalars():
        if s.lab_section:
            techs.setdefault(s.lab_section, []).append(s.display_name)

    may_reassign = has_permission(actor, "worklist.reassign")
    out: List[AssignedTestOrderResponse] = []
    for o in orders:
        line = o.invoice_line
        inv = line.invoice
        pat = inv.patient
        eff_status = "CANCELLED" if (line.status == "CANCELLED" or o.status == "CANCELLED") else o.status
        room_techs = techs.get(o.lab_section, []) if o.lab_section else []
        unassigned = o.status == "UNASSIGNED" or not o.lab_section or not room_techs
        blocked = reassign_block_reason(o)
        out.append(AssignedTestOrderResponse(
            test_order_id=o.id,
            invoice_id=inv.id,
            invoice_no=inv.invoice_no,
            patient_id=pat.id,
            patient_name=pat.name,
            patient_code=pat.patient_code,
            test_code=line.test_code_snapshot,
            test_name=line.test_name_snapshot,
            department=o.department or line.department_snapshot,
            lab_section=o.lab_section,
            lab_section_label=lab_section_label(o.lab_section),
            technician_names=[] if unassigned else list(room_techs),
            assignment_state="UNASSIGNED" if unassigned else "ASSIGNED",
            status=eff_status,
            urgent=bool(o.urgent),
            result_status=o.result.status if o.result else None,
            worked_by_name=o.assigned_to.display_name if o.assigned_to else None,
            created_at=o.created_at,
            can_reassign=bool(may_reassign and blocked is None),
            reassign_block_reason=blocked if may_reassign else "View only: moving an order needs the 'worklist.reassign' permission.",
        ))
    return out


def manually_assign_test_order(
    db: Session,
    tenant_id: str,
    data: ManualAssignRequest,
    assigner_id: int,
    acting_role: str = "RECEPTIONIST",
    can_reassign: bool = False,
) -> TestOrder:
    """Prompt 10E Part 7: assigns a test order to a ROOM (lab section), never to a technician.

    The destination may be a room key (HEMATOLOGY), a room/destination name ("Microbiology
    Lab 105") or a legacy test_destinations id; it is always resolved and stored as the room
    name, never as an id. UNASSIGNED orders can be assigned with 'assignment.manage'; moving an
    order that is already in progress in a room needs 'worklist.reassign'."""
    order = db.get(TestOrder, data.test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test order not found.",
        )
    section = None
    for candidate in (data.lab_section, data.assigned_destination, data.destination_name,
                      str(data.destination_id) if data.destination_id is not None else None):
        section = resolve_room(db, tenant_id, candidate)
        if section:
            break
    if not section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select a lab room (Hematology 101, Biochemistry 102, Microbiology 105 or Ultrasonography 204).",
        )
    if order.status != "UNASSIGNED" and not can_reassign:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This order is already routed. Moving it to another room needs the 'worklist.reassign' permission.",
        )
    return move_order_to_room(
        db, tenant_id, order, section, assigner_id, acting_role,
        reason=data.reason or "Assigned by front desk", action="ASSIGN_TEST_ORDER",
    )

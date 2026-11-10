from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.models.test_order import TestOrder, AssignmentHistory, TestOrderEvent
from backend.app.models.invoice import InvoiceLine, Invoice
from backend.app.models.patient import Patient
from backend.app.schemas.assignment import UnassignedOrderResponse, ManualAssignRequest
from backend.app.services.audit_service import log_audit_event


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
        )
        for o in orders
    ]


def manually_assign_test_order(
    db: Session,
    tenant_id: str,
    data: ManualAssignRequest,
    assigner_id: int,
    acting_role: str = "RECEPTIONIST",
) -> TestOrder:
    """Assigns an unassigned test order or logs reassignment."""
    order = db.get(TestOrder, data.test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test order not found.",
        )

    prev_destination = order.assigned_destination

    # Update order
    order.assigned_destination = data.assigned_destination.strip()
    order.assigned_to_id = data.assigned_to_id
    order.assigned_at = datetime.utcnow()
    order.assigned_by_id = assigner_id
    if order.status == "UNASSIGNED":
        order.status = "ASSIGNED"

    # Append assignment history log
    history = AssignmentHistory(
        tenant_id=tenant_id,
        test_order_id=order.id,
        previous_assignee=prev_destination,
        new_assignee=order.assigned_destination,
        reason=data.reason or "Assigned by front desk",
        changed_by_id=assigner_id,
    )
    db.add(history)

    # Append lifecycle event
    lifecycle_event = TestOrderEvent(
        tenant_id=tenant_id,
        test_order_id=order.id,
        event_type="REASSIGNED" if prev_destination else "ASSIGNED",
        stage=order.status,
        description=f"Task assigned to {order.assigned_destination} (previous: {prev_destination or 'UNASSIGNED'})",
        notes=data.reason,
        actor_id=assigner_id,
        actor_role=acting_role,
        created_at=datetime.utcnow(),
    )
    db.add(lifecycle_event)
    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="ASSIGN_TEST_ORDER",
        entity_type="TEST_ORDER",
        entity_id=order.id,
        acting_role=acting_role,
        actor_id=assigner_id,
        before_value=prev_destination or "UNASSIGNED",
        after_value=order.assigned_destination,
    )
    return order


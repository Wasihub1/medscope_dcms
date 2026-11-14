"""
MedScope DCMS — room-based routing (Prompt 10E Part 7).

Principle: a test order is routed to a ROOM (lab section, backend/app/core/lab_sections.py),
never to one specific technician. Every active LAB_TECH whose staff.lab_section equals the
order's room sees and works the order. assigned_to_id only records who actually acted.

- Finalize: the room comes from the test (tests.lab_section, else the mapping). Doctor-routed
  and outsourced tests keep their existing status (AWAITING_DOCTOR / PENDING); the room is
  still recorded. Otherwise ASSIGNED when the room has an active LAB_TECH, else UNASSIGNED.
- A room that gets its first active technician releases its UNASSIGNED orders automatically
  (status ASSIGNED, one audit row per order).
- Reassign (worklist.reassign): move an order to another room any time before COMPLETED.
- Prompt 10F (A11, owner decision "Unassigned thakbe"): when a room loses its last active
  technician, its orders that are only ASSIGNED (no sample, no result, no culture / outsourced
  step yet) become UNASSIGNED (room kept), one audit row each. Progress is never wiped.
"""
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from backend.app.core.lab_sections import (
    LAB_SECTIONS,
    lab_section_destination,
    lab_section_label,
    section_for_test,
    section_from_text,
)
from backend.app.core.permissions import has_permission
from backend.app.core.timezone import utc_now
from backend.app.models.invoice import InvoiceLine
from backend.app.models.test import Test, TestDestination
from backend.app.models.test_order import AssignmentHistory, TestOrder, TestOrderEvent
from backend.app.models.user import Staff
from backend.app.services.audit_service import log_audit_event

# Orders in these states are finished; routing never changes them.
TERMINAL_STATUSES = ("COMPLETED", "CANCELLED")
# Statuses that are re-evaluated between ASSIGNED and UNASSIGNED by routing.
ROUTABLE_STATUSES = ("ASSIGNED", "UNASSIGNED")


# ---------------------------------------------------------------------------
# Rooms and technicians
# ---------------------------------------------------------------------------
def active_technician_count(db: Session, tenant_id: str, section: Optional[str]) -> int:
    if not section:
        return 0
    return len(
        db.execute(
            select(Staff.id).where(
                Staff.tenant_id == tenant_id,
                Staff.active == True,  # noqa: E712
                Staff.deleted_at.is_(None),
                Staff.role == "LAB_TECH",
                Staff.lab_section == section,
            )
        ).all()
    )


def room_has_active_technician(db: Session, tenant_id: str, section: Optional[str]) -> bool:
    return active_technician_count(db, tenant_id, section) > 0


def list_rooms(db: Session, tenant_id: str) -> List[dict]:
    return [
        {
            "code": code,
            "name": sec["name"],
            "room": sec["room"],
            "destination": sec["destination"],
            "label": lab_section_label(code),
            "active_technicians": active_technician_count(db, tenant_id, code),
        }
        for code, sec in LAB_SECTIONS.items()
    ]


def resolve_room(db: Session, tenant_id: str, value: Optional[str]) -> Optional[str]:
    """Resolves a room key, room/destination name, or a legacy test_destinations id ("6")
    to a lab section code. Returns None when nothing matches."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    code = section_from_text(v)
    if code:
        return code
    if v.isdigit():
        dest = db.get(TestDestination, int(v))
        if dest and dest.tenant_id == tenant_id:
            return section_from_text(dest.name) or section_from_text(dest.department)
    return None


# ---------------------------------------------------------------------------
# Finalize routing
# ---------------------------------------------------------------------------
def route_new_order(db: Session, tenant_id: str, test: Test) -> Tuple[str, Optional[str], Optional[str], str]:
    """Returns (status, lab_section, assigned_destination, reason) for a new order."""
    section = section_for_test(test)
    room_name = lab_section_destination(section)
    if getattr(test, "requires_doctor", False) or (getattr(test, "performing_role", "") or "") == "DOCTOR":
        # Awaiting Doctor workflow unchanged; the room is recorded when the test maps to one.
        return "AWAITING_DOCTOR", section, (test.default_assignee or room_name or "Doctor Chamber"), \
            "Routed to Visiting Doctor Queue (Awaiting Doctor)"
    if getattr(test, "is_outsourced", False):
        return "PENDING", section, "Outsourced Referral Lab", "Marked for Outsourced Referral Processing"
    if section and room_has_active_technician(db, tenant_id, section):
        return "ASSIGNED", section, room_name, f"Routed to room {lab_section_label(section)}"
    if section:
        return "UNASSIGNED", section, room_name, f"Room {lab_section_label(section)} has no active technician"
    return "UNASSIGNED", None, None, "Test is not mapped to any lab room"


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------
def _doctor_queue_clause():
    doctor_routed = or_(
        TestOrder.performing_role == "DOCTOR",
        TestOrder.invoice_line.has(InvoiceLine.test.has(Test.requires_doctor == True)),  # noqa: E712
    )
    return or_(
        TestOrder.status == "AWAITING_DOCTOR",
        and_(TestOrder.status == "COMPLETED", doctor_routed),
    )


def visibility_clause(actor):
    """SQL condition limiting test orders to what the actor may see, or None for everything.
    Raises 403 when the actor may see nothing."""
    if has_permission(actor, "worklist.view_all"):
        return None
    clauses = []
    if has_permission(actor, "worklist.view") and getattr(actor, "lab_section", None):
        clauses.append(TestOrder.lab_section == actor.lab_section)
    if has_permission(actor, "worklist.doctor_queue"):
        clauses.append(_doctor_queue_clause())
    if not clauses:
        if has_permission(actor, "worklist.view"):
            # A worklist user without a room (e.g. legacy data) sees nothing rather than everything.
            return TestOrder.id == -1
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Laboratory worklist permission required.")
    return or_(*clauses)


def can_access_order(actor, order: TestOrder) -> bool:
    if has_permission(actor, "worklist.view_all"):
        return True
    if has_permission(actor, "worklist.view") and getattr(actor, "lab_section", None) and order.lab_section == actor.lab_section:
        return True
    if has_permission(actor, "worklist.doctor_queue"):
        if order.status == "AWAITING_DOCTOR":
            return True
        test = order.invoice_line.test if order.invoice_line else None
        if order.status == "COMPLETED" and (order.performing_role == "DOCTOR" or (test is not None and test.requires_doctor)):
            return True
    return False


def ensure_order_access(actor, order: TestOrder, message: str = "This order is not in your room.") -> None:
    if not can_access_order(actor, order):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def record_actor(order: TestOrder, actor) -> None:
    """assigned_to_id records who actually acted (technician); never used for visibility."""
    if getattr(actor, "role", None) == "LAB_TECH":
        order.assigned_to_id = actor.id


# ---------------------------------------------------------------------------
# Auto-release of UNASSIGNED orders when a room gets a technician
# ---------------------------------------------------------------------------
def release_unassigned_orders_for_section(
    db: Session,
    tenant_id: str,
    section: Optional[str],
    actor_id: Optional[int],
    acting_role: str,
    reason: str,
) -> int:
    """Promotes UNASSIGNED, non-terminal orders of `section` to ASSIGNED when the room has at
    least one active LAB_TECH. One audit row per promoted order. Returns the count."""
    if not section or not room_has_active_technician(db, tenant_id, section):
        return 0
    orders = db.execute(
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .where(
            TestOrder.tenant_id == tenant_id,
            TestOrder.lab_section == section,
            TestOrder.status == "UNASSIGNED",
            InvoiceLine.status != "CANCELLED",
        )
    ).scalars().all()
    now = utc_now()
    for o in orders:
        o.status = "ASSIGNED"
        o.assigned_destination = lab_section_destination(section)
        o.assigned_at = now
        if actor_id:
            o.assigned_by_id = actor_id
            db.add(AssignmentHistory(
                tenant_id=tenant_id, test_order_id=o.id, previous_assignee="UNASSIGNED",
                new_assignee=lab_section_destination(section) or section, reason=reason,
                changed_by_id=actor_id, changed_at=now,
            ))
        db.add(TestOrderEvent(
            tenant_id=tenant_id, test_order_id=o.id, event_type="ROOM_RELEASED", stage="ASSIGNED",
            description=f"Released to {lab_section_label(section)}: {reason}",
            actor_id=actor_id, actor_role=acting_role, created_at=now,
        ))
        log_audit_event(
            db=db, tenant_id=tenant_id, action="ORDER_ROOM_RELEASED", entity_type="TEST_ORDER",
            entity_id=o.id, acting_role=acting_role, actor_id=actor_id,
            before_value="UNASSIGNED", after_value=f"ASSIGNED to room {section} ({reason})",
        )
    db.flush()
    return len(orders)


# ---------------------------------------------------------------------------
# Prompt 10F (A11): a room that loses its last active technician
# ---------------------------------------------------------------------------
def demote_assigned_orders_if_room_empty(
    db: Session,
    tenant_id: str,
    section: Optional[str],
    actor_id: Optional[int],
    acting_role: str,
    reason: str,
) -> int:
    """Demotes the room's assigned-only orders to UNASSIGNED when `section` has no active LAB_TECH
    left. Call it after the staff change has been flushed, inside the same transaction.

    Demoted: status ASSIGNED with no sample row, no result (not even a DRAFT), no culture stage
    and no outsourced step, on a non-cancelled invoice line. Every other state (SAMPLE_PENDING,
    IN_PROGRESS, AWAITING_DOCTOR, PENDING, COMPLETED, CANCELLED, REJECTED/SPOILED, or ASSIGNED
    with any recorded work) is left exactly as it is. lab_section is kept, so the existing
    release (release_unassigned_orders_for_section) hands the orders back when a technician joins.
    One audit row ORDER_UNASSIGNED_ROOM_EMPTY + one event per order; an append-only assignment
    history row when the actor is a staff member. Returns the count."""
    if not section or room_has_active_technician(db, tenant_id, section):
        return 0
    from backend.app.models.result import Result
    from backend.app.models.sample import Sample

    orders = db.execute(
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .where(
            TestOrder.tenant_id == tenant_id,
            TestOrder.lab_section == section,
            TestOrder.status == "ASSIGNED",
            InvoiceLine.status != "CANCELLED",
            TestOrder.culture_stage.is_(None),
            TestOrder.outsourced_status.is_(None),
            ~exists().where(Sample.test_order_id == TestOrder.id),
            ~exists().where(Result.test_order_id == TestOrder.id),
        )
    ).scalars().all()
    now = utc_now()
    room_name = lab_section_destination(section) or section
    for o in orders:
        o.status = "UNASSIGNED"
        if actor_id:
            db.add(AssignmentHistory(
                tenant_id=tenant_id, test_order_id=o.id, previous_assignee=room_name,
                new_assignee="UNASSIGNED", reason=reason, changed_by_id=actor_id, changed_at=now,
            ))
        db.add(TestOrderEvent(
            tenant_id=tenant_id, test_order_id=o.id, event_type="ROOM_EMPTIED", stage="UNASSIGNED",
            description=f"{lab_section_label(section)} has no active technician: order is UNASSIGNED",
            notes=reason, actor_id=actor_id, actor_role=acting_role, created_at=now,
        ))
        log_audit_event(
            db=db, tenant_id=tenant_id, action="ORDER_UNASSIGNED_ROOM_EMPTY", entity_type="TEST_ORDER",
            entity_id=o.id, acting_role=acting_role, actor_id=actor_id,
            before_value=f"ASSIGNED to room {section}",
            after_value=f"UNASSIGNED (room {section} kept; {reason})",
        )
    db.flush()
    return len(orders)


def apply_technician_room_change(
    db: Session,
    tenant_id: str,
    old_section: Optional[str],
    old_counts: bool,
    new_section: Optional[str],
    new_counts: bool,
    actor_id: Optional[int],
    acting_role: str,
    who: str,
) -> Tuple[int, int]:
    """The one routine every staff change goes through (deactivate, reactivate, room change, role
    change, CLI). `*_counts` = the user was / is an active LAB_TECH. Must run after the staff row
    change is flushed, in the same transaction. Returns (demoted, released)."""
    demoted = released = 0
    if old_counts and old_section and not (new_counts and new_section == old_section):
        demoted = demote_assigned_orders_if_room_empty(
            db, tenant_id, old_section, actor_id, acting_role,
            f"{lab_section_label(old_section)} lost its last active technician ({who})",
        )
    if new_counts and new_section and not (old_counts and old_section == new_section):
        released = release_unassigned_orders_for_section(
            db, tenant_id, new_section, actor_id, acting_role,
            f"{lab_section_label(new_section)} gained an active technician ({who})",
        )
    return demoted, released


# ---------------------------------------------------------------------------
# Reassign / manual room assignment
# ---------------------------------------------------------------------------
NOT_PERFORMED_STATUSES = ("REJECTED", "SPOILED")


def reassign_block_reason(order: TestOrder) -> Optional[str]:
    """Why an order can no longer be moved to another room, or None when it can (Prompt 10F:
    the one rule used by the reassign endpoint, the Assign Tests list and the UI)."""
    if order.status == "COMPLETED":
        return "Completed: a COMPLETED order cannot be moved to another room."
    if order.status == "CANCELLED" or (order.invoice_line is not None and order.invoice_line.status == "CANCELLED"):
        return "Cancelled: a cancelled order cannot be moved to another room."
    if order.status in NOT_PERFORMED_STATUSES or (order.outcome or "") == "NOT_PERFORMED":
        return "Not performed: a rejected or spoiled order cannot be moved to another room."
    return None


def move_order_to_room(
    db: Session,
    tenant_id: str,
    order: TestOrder,
    to_section: str,
    actor_id: int,
    acting_role: str,
    reason: Optional[str] = None,
    action: str = "REASSIGN_ROOM",
) -> TestOrder:
    """Moves an order to `to_section` any time before COMPLETED. Results and samples already
    entered are kept. ASSIGNED/UNASSIGNED orders are re-evaluated for the new room; other
    in-flight statuses (IN_PROGRESS, AWAITING_DOCTOR, ...) are kept."""
    if to_section not in LAB_SECTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown room '{to_section}'.")
    blocked = reassign_block_reason(order)
    if blocked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocked)
    from_section = order.lab_section
    prev_status = order.status
    now = utc_now()
    order.lab_section = to_section
    order.assigned_destination = lab_section_destination(to_section)
    order.assigned_to_id = None  # the new room's technicians take over
    order.assigned_at = now
    order.assigned_by_id = actor_id
    if order.status in ROUTABLE_STATUSES:
        order.status = "ASSIGNED" if room_has_active_technician(db, tenant_id, to_section) else "UNASSIGNED"
    db.add(AssignmentHistory(
        tenant_id=tenant_id, test_order_id=order.id,
        previous_assignee=lab_section_destination(from_section) or (from_section or "UNASSIGNED"),
        new_assignee=lab_section_destination(to_section) or to_section,
        reason=reason or ("Room reassigned" if action == "REASSIGN_ROOM" else "Assigned to room"),
        changed_by_id=actor_id, changed_at=now,
    ))
    db.add(TestOrderEvent(
        tenant_id=tenant_id, test_order_id=order.id,
        event_type="REASSIGNED" if from_section else "ASSIGNED", stage=order.status,
        description=f"Room: {lab_section_label(from_section) or 'none'} -> {lab_section_label(to_section)}",
        notes=reason, actor_id=actor_id, actor_role=acting_role, created_at=now,
    ))
    log_audit_event(
        db=db, tenant_id=tenant_id, action=action, entity_type="TEST_ORDER", entity_id=order.id,
        acting_role=acting_role, actor_id=actor_id,
        before_value=f"room={from_section}, status={prev_status}",
        after_value=f"room={to_section}, status={order.status}, reason={reason or '-'}",
    )
    db.flush()
    return order

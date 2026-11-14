"""
MedScope DCMS - Doctor sign-off (Prompt 15, D22 / M14 approval half).

Two ways to record the doctor-side signature on a test whose approval rule is DOCTOR_REQUIRED or
BOTH_SIGNATURES, once the result is ENTERED:
  Path A  Admin / Owner records it on a doctor's behalf: picks the doctor, ticks the attestation.
          Required for visiting doctors, who have no login (D59).
  Path B  A DOCTOR login approves its own assigned orders directly.
Both write one doctor_approvals row (who clicked, which doctor, attestation flag, snapshots of the
doctor's name + registration number) and one audit row, in the same transaction.

Since Prompt 16 an approval also finalizes the report in the same transaction (report_finalization_service).
Not built here: reject / send back.
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.core.lab_sections import lab_section_label
from backend.app.core.permissions import has_permission
from backend.app.core.security import CurrentActor
from backend.app.core.timezone import utc_now
from backend.app.models.doctor_approval import DoctorApproval
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.referrer import Referrer
from backend.app.models.result import Result
from backend.app.models.sample import Sample
from backend.app.models.test import Test
from backend.app.models.test_order import TestOrder, TestOrderEvent
from backend.app.models.user import Staff
from backend.app.schemas.doctor_approval import (
    ApprovalDetailResponse, ApprovalQueueItem, ApprovalQueueResponse, ApprovalRecord, ApproveRequest, DoctorRef,
)
from backend.app.services.audit_service import log_audit_event
from backend.app.services.line_lock_service import lock_line_at_result_completion
from backend.app.services.ready_report_service import build_result_preview
from backend.app.services.report_finalization_service import try_auto_finalize

APPROVAL_PERMISSION = "result.complete_doctor_routed"  # reused key, see the Prompt 15 report
APPROVAL_RULES = ("DOCTOR_REQUIRED", "BOTH_SIGNATURES")
STAFF_ROLES = ("OWNER", "ADMIN")  # Path A
# Order states that can never be approved (cancelled / not performed).
DEAD_ORDER_STATUSES = ("CANCELLED", "REJECTED", "SPOILED")
# States an approval may be recorded in. COMPLETED covers doctor-routed orders completed before this
# screen existed (their result is ENTERED but no doctor signature was ever recorded).
APPROVABLE_ORDER_STATUSES = ("AWAITING_DOCTOR", "IN_PROGRESS", "COMPLETED")
# Referrer types that are not individual doctors.
NON_DOCTOR_TYPES = ("agent", "clinic", "institution", "other", "third party")


def _forbid(detail: str):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _conflict(detail: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _bad(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _ref(r: Optional[Referrer]) -> Optional[DoctorRef]:
    if r is None:
        return None
    return DoctorRef(id=r.id, name=r.name, registration_no=r.registration_no, specialty=r.specialty)


def _assigned(o: TestOrder) -> Optional[Referrer]:
    sess = Session.object_session(o)
    return sess.get(Referrer, o.assigned_doctor_id) if sess is not None and o.assigned_doctor_id else None


def _guard_actor(actor: CurrentActor) -> bool:
    """Returns True for Path B (DOCTOR login). Admin/Owner are Path A; every other role is refused,
    even when a per-user override grants them the permission key."""
    if not has_permission(actor, APPROVAL_PERMISSION):
        _forbid(f"Permission denied: '{APPROVAL_PERMISSION}' is required for this action.")
    if actor.role == "DOCTOR":
        return True
    if actor.role in STAFF_ROLES:
        return False
    _forbid("Only a doctor, an Admin or the Owner can record a doctor approval.")


def own_doctor_profile(db: Session, actor: CurrentActor) -> Optional[Referrer]:
    staff = db.get(Staff, actor.id)
    pid = getattr(staff, "doctor_profile_id", None)
    r = db.get(Referrer, pid) if pid else None
    if r is not None and (r.tenant_id != actor.tenant_id or r.deleted_at is not None):
        return None
    return r


def _check_doctor(db: Session, tenant_id: str, doctor_id: int) -> Referrer:
    r = db.get(Referrer, doctor_id)
    if r is None or r.tenant_id != tenant_id or r.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
    if not r.active:
        _conflict("This doctor is inactive.")
    if (r.referrer_type or "").strip().lower() in NON_DOCTOR_TYPES:
        _bad(f"'{r.name}' is a {r.referrer_type}, not an individual doctor.")
    if not (r.registration_no or "").strip():
        _conflict(f"{r.name} has no registration number on file. Add it to the doctor's profile first: "
                  "the report must print the doctor's name and registration number.")
    return r


def _pending_clause():
    """The one SQL definition of 'awaiting doctor sign-off'."""
    return and_(
        TestOrder.invoice_line.has(InvoiceLine.test.has(Test.approval_rule.in_(APPROVAL_RULES))),
        TestOrder.result.has(Result.status == "ENTERED"),
        ~TestOrder.doctor_approval.has(),
        TestOrder.status.not_in(DEAD_ORDER_STATUSES),
        or_(TestOrder.outcome.is_(None), TestOrder.outcome != "NOT_PERFORMED"),
        TestOrder.invoice_line.has(InvoiceLine.status != "CANCELLED"),
        ~TestOrder.sample.has(Sample.status.in_(("REJECTED", "SPOILED"))),
    )


def _item(o: TestOrder) -> ApprovalQueueItem:
    line = o.invoice_line
    inv = line.invoice
    pat = inv.patient
    res = o.result
    test = line.test
    return ApprovalQueueItem(
        test_order_id=o.id,
        invoice_no=inv.invoice_no,
        patient_name=pat.name,
        patient_code=pat.patient_code,
        test_code=line.test_code_snapshot,
        test_name=line.test_name_snapshot,
        department=o.department or line.department_snapshot,
        lab_section_label=lab_section_label(o.lab_section),
        approval_rule=test.approval_rule if test else "DOCTOR_REQUIRED",
        order_status=o.status,
        urgent=bool(o.urgent),
        technician_name=res.entered_by.display_name if res and res.entered_by else None,
        result_entered_at=(res.updated_at or res.entered_at) if res else None,
        assigned_doctor=_ref(_assigned(o)),
    )


def list_queue(db: Session, actor: CurrentActor, doctor_id: Optional[int] = None, query: Optional[str] = None,
               limit: int = 200) -> ApprovalQueueResponse:
    own = _guard_actor(actor)
    stmt = (
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .join(InvoiceLine.invoice)
        .join(Invoice.patient)
        .join(TestOrder.result)
        .where(TestOrder.tenant_id == actor.tenant_id, _pending_clause())
    )
    mine = None
    if own:
        mine = own_doctor_profile(db, actor)
        # A DOCTOR login only ever sees orders assigned to its own doctor profile.
        stmt = stmt.where(TestOrder.assigned_doctor_id == (mine.id if mine else -1))
    elif doctor_id:
        stmt = stmt.where(TestOrder.assigned_doctor_id == doctor_id)
    if query and query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(or_(
            Patient.name.ilike(q), Patient.patient_code.ilike(q), Patient.phone.ilike(q),
            Invoice.invoice_no.ilike(q), InvoiceLine.test_name_snapshot.ilike(q), InvoiceLine.test_code_snapshot.ilike(q),
        ))
    stmt = stmt.order_by(TestOrder.urgent.desc(), Result.updated_at.asc(), TestOrder.id.asc()).limit(limit)
    items = [_item(o) for o in db.execute(stmt).scalars().all()]
    return ApprovalQueueResponse(scope="OWN" if own else "ALL", my_doctor=_ref(mine), items=items)


def _load_order(db: Session, actor: CurrentActor, test_order_id: int, own: bool) -> TestOrder:
    o = db.get(TestOrder, test_order_id)
    if o is None or o.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")
    if own:
        # Scope by assignment first, so a doctor learns nothing about other doctors' orders.
        mine = own_doctor_profile(db, actor)
        if mine is None or o.assigned_doctor_id != mine.id:
            _forbid("This test order is not assigned to you.")
    test = o.invoice_line.test if o.invoice_line else None
    if test is None or test.approval_rule not in APPROVAL_RULES:
        _conflict("This test does not need a doctor approval (technician-final).")
    return o


def _approval_record(db: Session, a: DoctorApproval) -> ApprovalRecord:
    by = db.get(Staff, a.approved_by_user_id)
    return ApprovalRecord(
        id=a.id,
        doctor=DoctorRef(id=a.doctor_id, name=a.doctor_name, registration_no=a.doctor_registration_no),
        approved_by_user_id=a.approved_by_user_id,
        approved_by_name=by.display_name if by else None,
        approved_by_role=a.approved_by_role,
        is_attestation=a.is_attestation,
        notes=a.notes,
        approved_at=a.approved_at,
    )


def _blocker(order: TestOrder) -> Optional[str]:
    res = order.result
    if res is None or res.status != "ENTERED":
        return "The technician has not submitted the result yet."
    if order.status in DEAD_ORDER_STATUSES or order.outcome == "NOT_PERFORMED" or order.invoice_line.status == "CANCELLED":
        return "This test is cancelled or was not performed."
    if order.sample is not None and order.sample.status in ("REJECTED", "SPOILED"):
        return "The sample was rejected or spoiled."
    if order.status not in APPROVABLE_ORDER_STATUSES:
        return f"The order is in status {order.status}; it cannot be approved now."
    return None


def get_detail(db: Session, actor: CurrentActor, test_order_id: int) -> ApprovalDetailResponse:
    own = _guard_actor(actor)
    order = _load_order(db, actor, test_order_id, own)
    res = order.result
    if res is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No result has been saved for this order yet.")
    existing = order.doctor_approval
    blocker = "A doctor approval is already recorded." if existing else _blocker(order)
    return ApprovalDetailResponse(
        test_order_id=order.id,
        approval_rule=order.invoice_line.test.approval_rule,
        order_status=order.status,
        path="DOCTOR_OWN" if own else "STAFF_ATTESTATION",
        can_approve=blocker is None,
        blocked_reason=blocker,
        technician_name=res.entered_by.display_name if res.entered_by else None,
        technician_signed_at=res.updated_at or res.entered_at,
        assigned_doctor=_ref(_assigned(order)),
        my_doctor=_ref(own_doctor_profile(db, actor)) if own else None,
        approval=_approval_record(db, existing) if existing else None,
        preview=build_result_preview(db, actor.tenant_id, order.id),
    )


def assign_doctor(db: Session, actor: CurrentActor, test_order_id: int, doctor_id: Optional[int]) -> ApprovalQueueItem:
    """Admin/Owner put an order into one doctor's queue (or clear it). Audited."""
    own = _guard_actor(actor)
    if own:
        _forbid("Only an Admin or the Owner can assign an order to a doctor.")
    order = _load_order(db, actor, test_order_id, False)
    if order.doctor_approval is not None:
        _conflict("This order already has a doctor approval.")
    doc = _check_doctor(db, actor.tenant_id, doctor_id) if doctor_id else None
    before = _assigned(order)
    order.assigned_doctor_id = doc.id if doc else None
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action="DOCTOR_APPROVAL_ASSIGNED", entity_type="TEST_ORDER",
        entity_id=order.id, acting_role=actor.role, actor_id=actor.id,
        before_value=f"doctor={before.name}" if before else "unassigned",
        after_value=f"{actor.display_name} ({actor.role}) assigned the doctor sign-off to " + (doc.name if doc else "nobody"),
    )
    db.flush()
    return _item(order)


def approve(db: Session, actor: CurrentActor, test_order_id: int, data: ApproveRequest) -> ApprovalRecord:
    own = _guard_actor(actor)
    order = _load_order(db, actor, test_order_id, own)
    if order.doctor_approval is not None:
        _conflict("A doctor approval is already recorded for this test order.")
    blocker = _blocker(order)
    if blocker:
        _conflict(blocker)

    if own:
        mine = own_doctor_profile(db, actor)
        if mine is None:
            _conflict("Your login is not linked to a doctor profile yet. Ask the Owner or an Admin to link it.")
        doctor = _check_doctor(db, actor.tenant_id, mine.id)
        attestation = False
    else:
        if not data.doctor_id:
            _bad("Select the doctor this approval is for.")
        if not data.attestation:
            _bad("The attestation must be ticked: confirm that the doctor has reviewed and approved this result.")
        doctor = _check_doctor(db, actor.tenant_id, data.doctor_id)
        attestation = True

    now = utc_now()
    test = order.invoice_line.test
    notes = (data.notes or "").strip() or None
    row = DoctorApproval(
        tenant_id=actor.tenant_id, test_order_id=order.id, result_id=order.result.id, approval_rule=test.approval_rule,
        doctor_id=doctor.id, doctor_name=doctor.name, doctor_registration_no=doctor.registration_no.strip(),
        approved_by_user_id=actor.id, approved_by_role=actor.role, is_attestation=attestation, notes=notes, approved_at=now,
    )
    db.add(row)

    # Move the order on with the existing completion step (same rules as a technician-final completion).
    # Culture tests stay open until the culture stage is FINAL.
    before_status = order.status
    is_culture = (test.report_template == "CULTURE_SENSITIVITY") or (order.culture_stage is not None)
    if order.status in ("AWAITING_DOCTOR", "IN_PROGRESS") and not (is_culture and order.culture_stage != "FINAL"):
        order.status = "COMPLETED"
        lock_line_at_result_completion(order, now)
    if order.assigned_doctor_id is None:
        order.assigned_doctor_id = doctor.id

    if attestation:
        action = "DOCTOR_APPROVAL_RECORDED_BY_STAFF"
        summary = (f"Staff {actor.display_name} ({actor.role}) recorded approval on behalf of {doctor.name} "
                   f"(Reg {row.doctor_registration_no}), attestation ticked")
        desc = f"Doctor approval recorded by {actor.display_name} ({actor.role}) on behalf of {doctor.name}"
    else:
        action = "DOCTOR_APPROVED_OWN_RESULT"
        summary = f"{doctor.name} (Reg {row.doctor_registration_no}) approved own result, logged in as {actor.display_name}"
        desc = f"{doctor.name} approved the result"
    if notes:
        summary += f" | notes: {notes}"
    db.add(TestOrderEvent(
        tenant_id=actor.tenant_id, test_order_id=order.id, event_type="DOCTOR_APPROVED", stage=order.status,
        description=desc, notes=notes, actor_id=actor.id, actor_name=actor.display_name, actor_role=actor.role, created_at=now,
    ))
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action=action, entity_type="TEST_ORDER", entity_id=order.id,
        acting_role=actor.role, actor_id=actor.id, before_value=f"status={before_status}, no doctor approval",
        after_value=f"{summary} | rule={row.approval_rule}, status={order.status}",
    )
    db.flush()
    # Module 14 (Prompt 16): the approval is the finalization for doctor-required and both-signature tests.
    # It happens here, in the same transaction, so there is no second click and no half-approved state.
    # Cultures not yet at stage FINAL are finalized later, when the stage reaches FINAL.
    try_auto_finalize(db, actor, order)
    return _approval_record(db, row)

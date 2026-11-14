"""
MedScope DCMS - Module 14 (Prompt 16): Draft -> Final report.

Draft = a result saved with status DRAFT (results.status, Module 13). It has no report_versions row.
Final = one report_versions row (status FINAL_AUTHORIZED) holding an immutable content snapshot.

Who finalizes (D22):
  TECHNICIAN_FINAL  explicit Finalize click once the result is ENTERED (POST /worklist/{id}/finalize-report).
  DOCTOR_REQUIRED   automatic, in the same transaction as the doctor approval (doctor_approval_service).
  BOTH_SIGNATURES   automatic, in the doctor-approval transaction, and only when the technician sign-off
                    (the ENTERED result) is also present.
Cultures additionally wait for culture_stage FINAL: a doctor approval given earlier finalizes
automatically when the stage reaches FINAL; a technician-final culture needs the explicit click then.

COMPLETED on a test order stays an operational status; it is never read as "the report is Final".
Not built here: corrections / new versions (Module 15), real SMS / QR / PDF (Modules 25 / 9 / 26).
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.timezone import utc_now
from backend.app.models.doctor_approval import DoctorApproval
from backend.app.models.report import NotificationLog, ReportVersion
from backend.app.models.test_order import TestOrder, TestOrderEvent
from backend.app.services.audit_service import log_audit_event
from backend.app.services.line_lock_service import lock_line_at_result_completion
from backend.app.services.sequence_service import generate_report_number

FINAL_STATUS = "FINAL_AUTHORIZED"
DOCTOR_RULES = ("DOCTOR_REQUIRED", "BOTH_SIGNATURES")
DEAD_ORDER_STATUSES = ("CANCELLED", "REJECTED", "SPOILED")


def final_report_of(order: TestOrder) -> Optional[ReportVersion]:
    rv = order.report_version
    return rv if rv is not None and rv.status == FINAL_STATUS else None


def _approval_of(db: Session, order: TestOrder) -> Optional[DoctorApproval]:
    return db.execute(select(DoctorApproval).where(DoctorApproval.test_order_id == order.id)).scalar_one_or_none()


def finalize_blocker(db: Session, order: TestOrder) -> Optional[str]:
    """None when the report can be finalized now, otherwise the plain reason it cannot."""
    if final_report_of(order) is not None:
        return "This report is already Final."
    line = order.invoice_line
    test = line.test if line else None
    if test is None:
        return "The test is missing from the catalog."
    if order.status in DEAD_ORDER_STATUSES or order.outcome == "NOT_PERFORMED" or line.status == "CANCELLED":
        return "This test is cancelled or was not performed."
    if order.sample is not None and order.sample.status in ("REJECTED", "SPOILED"):
        return "The sample was rejected or spoiled."
    res = order.result
    if res is None or res.status != "ENTERED":
        return "The result has not been submitted yet (a draft cannot be finalized)."
    if test.approval_rule in DOCTOR_RULES and _approval_of(db, order) is None:
        return "Waiting for the doctor's approval."
    is_culture = test.report_template == "CULTURE_SENSITIVITY" or order.culture_stage is not None
    if is_culture and order.culture_stage != "FINAL":
        return f"The culture is still at the {order.culture_stage or 'INCUBATING'} stage; it must reach FINAL first."
    return None


def finalize_report(db: Session, actor, order: TestOrder, automatic: bool = False) -> ReportVersion:
    """Creates the Final report version. Raises 409 with the blocker when not allowed.
    The caller commits (so an automatic finalization shares the approval's transaction)."""
    blocker = finalize_blocker(db, order)
    if blocker:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=blocker)

    from backend.app.services.ready_report_service import build_result_preview  # avoid an import cycle

    now = utc_now()
    line = order.invoice_line
    test = line.test
    res = order.result
    approval = _approval_of(db, order)

    # The operational status follows the report: a Final report's order is COMPLETED (line locked).
    if order.status in ("IN_PROGRESS", "AWAITING_DOCTOR"):
        order.status = "COMPLETED"
    lock_line_at_result_completion(order, now)

    snapshot = build_result_preview(db, order.tenant_id, order.id).model_dump(mode="json")
    snapshot["is_draft"] = False
    snapshot["is_ready"] = False
    snapshot["order_status"] = order.status
    tech = res.updated_by or res.entered_by
    signatures = {
        "technician": {
            "name": tech.display_name if tech else None,
            "role": tech.role if tech else None,
            "signed_at": (res.updated_at or res.entered_at).isoformat(),
        },
        "doctor": None,
    }
    if approval is not None:
        signatures["doctor"] = {
            "name": approval.doctor_name,
            "registration_no": approval.doctor_registration_no,
            "approved_at": approval.approved_at.isoformat(),
            "recorded_by_user_id": approval.approved_by_user_id,
            "recorded_by_role": approval.approved_by_role,
            "is_attestation": approval.is_attestation,
        }
    summary = (res.impression or res.findings or "").strip() or None

    rv = ReportVersion(
        tenant_id=order.tenant_id,
        test_order_id=order.id,
        report_no=generate_report_number(line.invoice.invoice_no, line.id),
        version=1,  # Module 15 (corrections) will add later versions
        status=FINAL_STATUS,
        authorized=True,
        findings_summary=summary[:2000] if summary else None,
        issued_at=now,
        issued_by_id=actor.id,
        result_id=res.id,
        approval_rule=test.approval_rule,
        doctor_approval_id=approval.id if approval else None,
        content_snapshot=snapshot,
        signatures=signatures,
    )
    db.add(rv)
    db.flush()
    db.refresh(order)

    # Placeholder for the report-ready SMS (Module 25, D63): a row saying a notification is DUE. Nothing is sent.
    db.add(NotificationLog(
        tenant_id=order.tenant_id, kind="REPORT_READY_SMS", status="PENDING_INTEGRATION",
        report_version_id=rv.id, patient_id=line.invoice.patient_id,
        note="Report-ready notification due; no SMS gateway is integrated (placeholder only).",
    ))
    db.add(TestOrderEvent(
        tenant_id=order.tenant_id, test_order_id=order.id, event_type="REPORT_FINALIZED", stage=order.status,
        description=f"Report {rv.report_no} finalized by {actor.display_name} ({actor.role})"
                    + (" together with the doctor approval" if automatic else ""),
        actor_id=actor.id, actor_name=actor.display_name, actor_role=actor.role, created_at=now,
    ))
    log_audit_event(
        db=db, tenant_id=order.tenant_id, action="REPORT_FINALIZED", entity_type="REPORT_VERSION", entity_id=rv.id,
        acting_role=actor.role, actor_id=actor.id,
        before_value="DRAFT / ENTERED result",
        after_value=f"Final {rv.report_no} v1, rule={test.approval_rule}, test_order={order.id}"
                    + (", automatic on doctor approval" if automatic else ", explicit Finalize"),
    )
    log_audit_event(
        db=db, tenant_id=order.tenant_id, action="REPORT_READY_NOTIFICATION_DUE", entity_type="REPORT_VERSION",
        entity_id=rv.id, acting_role=actor.role, actor_id=actor.id,
        after_value="Report-ready SMS is due (PENDING_INTEGRATION); no SMS was sent.",
    )
    return rv


def try_auto_finalize(db: Session, actor, order: TestOrder) -> Optional[ReportVersion]:
    """Used by the doctor approval and the culture FINAL step: finalizes only when every condition is met,
    otherwise does nothing (the approval or stage change itself must not fail because of it)."""
    test = order.invoice_line.test if order.invoice_line else None
    if test is None or test.approval_rule not in DOCTOR_RULES:
        return None
    if finalize_blocker(db, order) is not None:
        return None
    return finalize_report(db, actor, order, automatic=True)

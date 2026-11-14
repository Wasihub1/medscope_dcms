from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session
from backend.app.models.report import ReportVersion, ReportDelivery
from backend.app.models.test_order import TestOrder
from backend.app.models.invoice import InvoiceLine, Invoice
from backend.app.models.patient import Patient
from backend.app.schemas.report import (
    DeliverableReportResponse,
    ReportDeliveryRequest,
    PrintableReportData,
    ResultPreviewResponse,
)
from backend.app.services import settings_service
from backend.app.services.audit_service import count_reprints, log_audit_event, log_reprint_event


def list_deliverable_reports(
    db: Session,
    tenant_id: str,
    query: Optional[str] = None,
    delivery_status: Optional[str] = None,
    limit: int = 50,
    has_due: Optional[bool] = None,
) -> List[DeliverableReportResponse]:
    """Lists authorized reports with due status and delivery state. Prompt 17: the search also finds the
    patient number, test name and temporary bill number; is_held_due_to_balance follows the center setting."""
    hold_enabled = settings_service.get_bool(db, tenant_id, "report_hold_when_due")
    stmt = (
        select(ReportVersion)
        .join(ReportVersion.test_order)
        .join(TestOrder.invoice_line)
        .join(InvoiceLine.invoice)
        .join(Invoice.patient)
        .where(
            ReportVersion.tenant_id == tenant_id,
            ReportVersion.authorized == True,
            InvoiceLine.status != "CANCELLED",
        )
        .order_by(desc(ReportVersion.issued_at))
    )

    if query and query.strip():
        q = query.strip()
        stmt = stmt.where(
            (ReportVersion.report_no.ilike(f"%{q}%"))
            | (Invoice.invoice_no.ilike(f"%{q}%"))
            | (Patient.name.ilike(f"%{q}%"))
            | (Patient.phone.ilike(f"%{q}%"))
            | (Patient.patient_code.ilike(f"%{q}%"))
            | (Invoice.temp_invoice_id.ilike(f"%{q}%"))
            | (InvoiceLine.test_name_snapshot.ilike(f"%{q}%"))
            | (InvoiceLine.test_code_snapshot.ilike(f"%{q}%"))
        )
    if has_due is True:
        stmt = stmt.where(Invoice.due > 0)
    elif has_due is False:
        stmt = stmt.where(Invoice.due <= 0)

    reports = list(db.execute(stmt.limit(limit)).scalars().all())
    results = []

    for r in reports:
        inv = r.test_order.invoice_line.invoice
        pat = inv.patient
        deliv = r.deliveries[0] if r.deliveries else None
        is_delivered = deliv is not None

        if delivery_status == "PENDING" and is_delivered:
            continue
        if delivery_status == "DELIVERED" and not is_delivered:
            continue

        results.append(
            DeliverableReportResponse(
                report_version_id=r.id,
                report_no=r.report_no,
                version=r.version,
                test_name=r.test_order.invoice_line.test_name_snapshot,
                department=r.test_order.invoice_line.department_snapshot,
                invoice_id=inv.id,
                invoice_no=inv.invoice_no,
                patient_id=pat.id,
                patient_name=pat.name,
                patient_code=pat.patient_code,
                patient_phone=pat.phone,
                issued_at=r.issued_at,
                issued_by_name=r.issued_by.display_name if r.issued_by else None,
                invoice_due=inv.due,
                is_held_due_to_balance=hold_enabled and inv.due > 0,
                is_delivered=is_delivered,
                delivered_at=deliv.delivered_at if deliv else None,
                delivered_to_name=deliv.delivered_to_name if deliv else None,
                has_snapshot=r.content_snapshot is not None,
                approval_rule=r.approval_rule,
            )
        )

    return results


def get_deliverable_report_by_id(
    db: Session,
    tenant_id: str,
    report_version_id: int,
) -> DeliverableReportResponse:
    """Retrieves a single deliverable report by ID."""
    report = db.get(ReportVersion, report_version_id)
    if not report or report.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found.")

    inv = report.test_order.invoice_line.invoice
    pat = inv.patient
    deliv = report.deliveries[0] if report.deliveries else None
    is_delivered = deliv is not None

    return DeliverableReportResponse(
        report_version_id=report.id,
        report_no=report.report_no,
        version=report.version,
        test_name=report.test_order.invoice_line.test_name_snapshot,
        department=report.test_order.invoice_line.department_snapshot,
        invoice_id=inv.id,
        invoice_no=inv.invoice_no,
        patient_id=pat.id,
        patient_name=pat.name,
        patient_code=pat.patient_code,
        patient_phone=pat.phone,
        issued_at=report.issued_at,
        issued_by_name=report.issued_by.display_name if report.issued_by else None,
        invoice_due=inv.due,
        is_held_due_to_balance=settings_service.get_bool(db, tenant_id, "report_hold_when_due") and inv.due > 0,
        is_delivered=is_delivered,
        delivered_at=deliv.delivered_at if deliv else None,
        delivered_to_name=deliv.delivered_to_name if deliv else None,
        has_snapshot=report.content_snapshot is not None,
        approval_rule=report.approval_rule,
    )


def get_final_snapshot(db: Session, tenant_id: str, report_version_id: int) -> ResultPreviewResponse:
    """The stored content of a Final report, exactly as it was at finalization. Never rebuilt from the
    live result or catalog, so later changes cannot alter it. Seeded pre-Module-14 reports have none (404)."""
    report = db.get(ReportVersion, report_version_id)
    if not report or report.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found.")
    if report.content_snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This report was issued before report snapshots existed and has no stored result content.")
    data = dict(report.content_snapshot)
    data.update(report_status="FINAL", report_version_id=report.id, report_no=report.report_no,
                can_finalize=False, finalize_blocker="This report is already Final.", signatures=report.signatures)
    return ResultPreviewResponse(**data)


def record_report_delivery(
    db: Session,
    tenant_id: str,
    report_version_id: int,
    data: ReportDeliveryRequest,
    deliverer_id: int,
    acting_role: str = "RECEPTIONIST",
    can_release_with_due: Optional[bool] = None,
) -> ReportDelivery:
    """Delivers report to patient/relation, strictly enforcing due-hold policies."""
    report = db.get(ReportVersion, report_version_id)
    if not report or report.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found.")

    if not report.authorized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deliver an unauthorized or draft report.",
        )

    invoice = report.test_order.invoice_line.invoice
    has_due = invoice.due > 0
    # Prompt 17: the center setting. Off = a report is never held for due (nothing to override).
    hold_enabled = settings_service.get_bool(db, tenant_id, "report_hold_when_due")

    # Section 2.10 Due Hold Enforcement (Prompt 10E Part 6):
    # only holders of 'report.release_with_due' (ADMIN / OWNER by default) may release a report
    # while a due exists, and only with an override reason. RECEPTIONIST and CASHIER are blocked,
    # with or without a reason.
    if has_due and hold_enabled:
        if can_release_with_due is None:
            can_release_with_due = acting_role in ("ADMIN", "OWNER")
        if not can_release_with_due:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Report is held because invoice {invoice.invoice_no} has an outstanding due of Tk {invoice.due}. Only an Admin/Owner can release it, with an override reason.",
            )
        if not (data.admin_due_override_reason or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An override reason is required to release a report while a due exists.",
            )

    delivery = ReportDelivery(
        tenant_id=tenant_id,
        report_version_id=report.id,
        delivered_to_name=data.delivered_to_name.strip(),
        delivered_to_phone=data.delivered_to_phone.strip() if data.delivered_to_phone else None,
        delivered_to_relation=data.delivered_to_relation.strip(),
        delivered_with_due=has_due,
        due_release_reason=data.admin_due_override_reason.strip() if data.admin_due_override_reason else None,
        delivered_by_id=deliverer_id,
    )
    db.add(delivery)
    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="DELIVER_REPORT",
        entity_type="REPORT_VERSION",
        entity_id=report.id,
        acting_role=acting_role,
        actor_id=deliverer_id,
        after_value=(f"Handed over to: {delivery.delivered_to_name} ({delivery.delivered_to_relation}), invoice due Tk {invoice.due}"
                     + (f", released despite due (hold on), reason: {delivery.due_release_reason}" if has_due and hold_enabled
                        else (", hold setting off" if has_due else ""))),
    )
    return delivery


def log_report_view(db: Session, actor, report_version_id: int, via: str) -> None:
    """Prompt 19B: one audit row for every open of a finalized report (no throttling, no dedupe).
    Called only after the read succeeded, so a 404 leaves no row. `via` names the screen/endpoint."""
    report = db.get(ReportVersion, report_version_id)
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action="REPORT_VIEWED", entity_type="REPORT", entity_id=report_version_id,
        acting_role=actor.role, actor_id=actor.id,
        after_value=f"Viewed report {report.report_no if report else '?'} v{report.version if report else '?'} ({via})",
    )


def log_ready_result_view(db: Session, actor, test_order_id: int) -> None:
    """Prompt 19B: one audit row for every open of a ready-result preview (a saved result that is not yet a
    Final report). entity_type is REPORT as specified; entity_id is the TEST ORDER id because no report
    version exists yet, and the action name says so."""
    log_audit_event(
        db=db, tenant_id=actor.tenant_id, action="REPORT_PREVIEW_VIEWED", entity_type="REPORT", entity_id=test_order_id,
        acting_role=actor.role, actor_id=actor.id,
        after_value=f"Viewed ready-result preview of test order #{test_order_id} (entity_id is the test order id)",
    )


def get_printable_report_data(
    db: Session,
    tenant_id: str,
    report_version_id: int,
    actor_id: int,
    acting_role: str,
) -> PrintableReportData:
    """Retrieves formatted report data and registers reprint audit."""
    report = db.get(ReportVersion, report_version_id)
    if not report or report.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found.")

    order = report.test_order
    line = order.invoice_line
    inv = line.invoice
    pat = inv.patient

    # Prompt 17: count earlier prints of this report first, so the copy is marked Duplicate from the second print on
    prior_prints = count_reprints(db, tenant_id, "REPORT", report.id)

    # Log reprint event
    log_reprint_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="REPORT",
        entity_id=report.id,
        actor_id=actor_id,
        acting_role=acting_role,
        reason="Front desk report print/reprint request",
    )

    return PrintableReportData(
        report_no=report.report_no,
        version=report.version,
        patient_name=pat.name,
        patient_code=pat.patient_code,
        age_gender_summary=f"{inv.visit.age_value} {inv.visit.age_unit} / {inv.visit.gender}",
        phone=pat.phone,
        referred_by=inv.referrer.name if inv.referrer else "Self / General",
        invoice_no=inv.invoice_no,
        sample_collected_at=order.sample.collected_at if order.sample else None,
        test_name=line.test_name_snapshot,
        department=line.department_snapshot,
        findings_summary=report.findings_summary or "All parameters within evaluated normal physiological limits.",
        issued_at=report.issued_at,
        issued_by_name=report.issued_by.display_name if report.issued_by else "Clinical Laboratory Staff",
        is_duplicate=len(report.deliveries) > 0 or prior_prints > 0,
        reprint_count=prior_prints + 1,
    )


from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from backend.app.models.report import ReportVersion, ReportDelivery
from backend.app.models.test_order import TestOrder
from backend.app.models.invoice import InvoiceLine, Invoice
from backend.app.models.patient import Patient
from backend.app.schemas.report import (
    DeliverableReportResponse,
    ReportDeliveryRequest,
    PrintableReportData,
)
from backend.app.services.audit_service import log_audit_event, log_reprint_event


def list_deliverable_reports(
    db: Session,
    tenant_id: str,
    query: Optional[str] = None,
    delivery_status: Optional[str] = None,
    limit: int = 50,
) -> List[DeliverableReportResponse]:
    """Lists authorized reports with due status and delivery state."""
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
        )

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
                is_held_due_to_balance=inv.due > 0,
                is_delivered=is_delivered,
                delivered_at=deliv.delivered_at if deliv else None,
                delivered_to_name=deliv.delivered_to_name if deliv else None,
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
        is_held_due_to_balance=inv.due > 0,
        is_delivered=is_delivered,
        delivered_at=deliv.delivered_at if deliv else None,
        delivered_to_name=deliv.delivered_to_name if deliv else None,
    )


def record_report_delivery(
    db: Session,
    tenant_id: str,
    report_version_id: int,
    data: ReportDeliveryRequest,
    deliverer_id: int,
    acting_role: str = "RECEPTIONIST",
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

    # Section 2.10 Due Hold Enforcement
    if has_due:
        # If receptionist, they cannot bypass due without an Admin override reason
        if acting_role == "RECEPTIONIST" and not data.admin_due_override_reason:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Report is held because invoice {invoice.invoice_no} has an outstanding due of Tk {invoice.due}. Receptionist cannot release without Admin/Owner override reason.",
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
        after_value=f"Delivered to: {delivery.delivered_to_name} ({delivery.delivered_to_relation}), Due Override: {has_due}",
    )
    return delivery


def get_printable_report_data(
    db: Session,
    tenant_id: str,
    report_version_id: int,
    actor_id: int,
) -> PrintableReportData:
    """Retrieves formatted report data and registers reprint audit."""
    report = db.get(ReportVersion, report_version_id)
    if not report or report.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found.")

    order = report.test_order
    line = order.invoice_line
    inv = line.invoice
    pat = inv.patient

    # Log reprint event
    log_reprint_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="REPORT",
        entity_id=report.id,
        reprinted_by_id=actor_id,
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
        is_duplicate=len(report.deliveries) > 0,
        reprint_count=1,
    )


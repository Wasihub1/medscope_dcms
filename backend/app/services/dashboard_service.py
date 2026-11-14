from datetime import datetime, time
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
from backend.app.core.timezone import to_dhaka_time
from backend.app.models.patient import Patient
from backend.app.models.invoice import Invoice
from backend.app.models.payment import Payment
from backend.app.models.test_order import TestOrder
from backend.app.models.report import ReportVersion, ReportDelivery
from backend.app.models.refund import RefundRequest
from backend.app.models.business_day import BusinessDay
from backend.app.schemas.dashboard import (
    ReceptionistDashboardResponse,
    BentoTileStats,
)
from backend.app.schemas.invoice import InvoiceResponse
from backend.app.services.business_day_service import get_business_day_status


def get_receptionist_dashboard_data(
    db: Session,
    tenant_id: str,
) -> ReceptionistDashboardResponse:
    """Computes all live operational statistics for the Bento Grid Dashboard."""
    # 1. Determine active business day or today's window
    b_status = get_business_day_status(db, tenant_id)
    now_dhaka = to_dhaka_time(datetime.utcnow())
    today_start = datetime.combine(now_dhaka.date(), time.min)

    # 2. Today's patients
    stmt_p = select(func.count(Patient.id)).where(
        Patient.tenant_id == tenant_id,
        Patient.created_at >= today_start,
    )
    today_patients = db.execute(stmt_p).scalar_one()

    # 3. Today's confirmed invoices
    stmt_i = select(func.count(Invoice.id)).where(
        Invoice.tenant_id == tenant_id,
        Invoice.status == "CONFIRMED",
        Invoice.created_at >= today_start,
    )
    today_invoices = db.execute(stmt_i).scalar_one()

    # 4. Payments collected in active day session (or today if no session open)
    if b_status.is_open and b_status.current_business_day_id:
        stmt_pay = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.business_day_id == b_status.current_business_day_id,
        )
    else:
        stmt_pay = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == tenant_id,
            Payment.received_at >= today_start,
        )
    payments_collected = db.execute(stmt_pay).scalar_one()

    # 5. Total outstanding dues
    stmt_due = select(func.coalesce(func.sum(Invoice.due), 0)).where(
        Invoice.tenant_id == tenant_id,
        Invoice.due > 0,
        Invoice.status.not_in(["CANCELLED", "DRAFT"]),
    )
    outstanding_dues = db.execute(stmt_due).scalar_one()

    # 6. Unassigned tests count
    stmt_unassigned = select(func.count(TestOrder.id)).where(
        TestOrder.tenant_id == tenant_id,
        TestOrder.status == "UNASSIGNED",
    )
    unassigned_count = db.execute(stmt_unassigned).scalar_one()

    # 7. Reports ready for delivery & held due to balance
    stmt_ready = (
        select(ReportVersion)
        .join(ReportVersion.test_order)
        .where(
            ReportVersion.tenant_id == tenant_id,
            ReportVersion.authorized == True,
            ~ReportVersion.deliveries.any(),  # Not yet delivered
        )
    )
    undelivered_reports = list(db.execute(stmt_ready).scalars().all())
    ready_count = 0
    held_count = 0
    held_summaries = []

    for rep in undelivered_reports:
        inv = rep.test_order.invoice_line.invoice
        if inv.due > 0:
            held_count += 1
            if len(held_summaries) < 5:
                held_summaries.append({
                    "report_no": rep.report_no,
                    "patient_name": inv.patient.name,
                    "test_name": rep.test_order.invoice_line.test_name_snapshot,
                    "due": inv.due,
                    "invoice_no": inv.invoice_no,
                })
        else:
            ready_count += 1

    # 8. Pending refund requests
    stmt_refunds = select(func.count(RefundRequest.id)).where(
        RefundRequest.tenant_id == tenant_id,
        RefundRequest.status == "PENDING_ADMIN_APPROVAL",
    )
    pending_refunds = db.execute(stmt_refunds).scalar_one()

    # 9. Recent Invoices
    stmt_recent = (
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.status != "DRAFT")
        .order_by(desc(Invoice.created_at))
        .limit(8)
    )
    recent_invoices_raw = list(db.execute(stmt_recent).scalars().all())
    recent_invoices = [
        InvoiceResponse(
            id=inv.id,
            invoice_no=inv.invoice_no,
            temp_invoice_id=inv.temp_invoice_id,
            patient_id=inv.patient_id,
            visit_id=inv.visit_id,
            referrer_id=inv.referrer_id,
            referrer_name=inv.referrer.name if inv.referrer else None,
            status=inv.status,
            payment_status=inv.payment_status,
            gross=inv.gross,
            discount=inv.discount,
            net=inv.net,
            paid=inv.paid,
            due=inv.due,
            refund_due=inv.refund_due,
            urgent=inv.urgent,
            created_at=inv.created_at,
            created_by_name=inv.created_by.display_name if inv.created_by else None,
            patient_name=inv.patient.name,
            patient_code=inv.patient.patient_code,
            patient_phone=inv.patient.phone,
        )
        for inv in recent_invoices_raw
    ]

    stats = BentoTileStats(
        today_patients_count=today_patients,
        today_invoices_count=today_invoices,
        today_payments_collected=payments_collected,
        total_outstanding_dues=outstanding_dues,
        unassigned_tests_count=unassigned_count,
        reports_ready_for_delivery=ready_count,
        reports_held_due_to_balance=held_count,
        pending_refund_requests_count=pending_refunds,
    )

    return ReceptionistDashboardResponse(
        stats=stats,
        business_day=b_status,
        recent_invoices=recent_invoices,
        active_unassigned_summary=[],
        held_reports_summary=held_summaries,
    )


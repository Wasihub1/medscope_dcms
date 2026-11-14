"""
MedScope DCMS — Ready results and the read-only result preview (Prompt 10F, F2/F3).

ONE definition of "Ready" (ready_clause) is used by:
- the Lab "Ready Reports" tile count (worklist summary),
- the Lab "Ready Reports" tab / tile list (worklist status=READY) and the row flag report_ready,
- the sidebar Ready Reports list (GET /reports/ready).

Ready (owner expectation, Prompt 10F): the result status is ENTERED (submitted, not merely DRAFT)
and the order is not cancelled (order or invoice line), not Not Performed (REJECTED / SPOILED or
outcome NOT_PERFORMED, or a rejected/spoiled sample) and not AWAITING_DOCTOR. Completing the order
operationally is NOT required.

Ready is not an issued report: no report_versions row is created here. Finalizing (Module 14) creates the
Final report, and the order then leaves Ready.
"""
from typing import Iterable, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.lab_sections import lab_section_label
from backend.app.core.permissions import has_permission, is_money_restricted
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.patient import Patient
from backend.app.models.report import ReportVersion
from backend.app.models.result import Result
from backend.app.models.sample import Sample
from backend.app.models.test_order import TestOrder
from backend.app.services.report_finalization_service import final_report_of, finalize_blocker
from backend.app.schemas.report import ReadyReportResponse, ResultPreviewItem, ResultPreviewResponse

# Order states that are never Ready, even with an ENTERED result.
NOT_READY_ORDER_STATUSES = ("CANCELLED", "REJECTED", "SPOILED", "AWAITING_DOCTOR")


def ready_clause():
    """The single SQL definition of a Ready result (see the module docstring)."""
    return and_(
        TestOrder.result.has(Result.status == "ENTERED"),
        TestOrder.status.not_in(NOT_READY_ORDER_STATUSES),
        or_(TestOrder.outcome.is_(None), TestOrder.outcome != "NOT_PERFORMED"),
        TestOrder.invoice_line.has(InvoiceLine.status != "CANCELLED"),
        ~TestOrder.sample.has(Sample.status.in_(("REJECTED", "SPOILED"))),
        # Module 14 (Prompt 16): a result that already has a Final report is Issued, not Ready, in every list.
        ~TestOrder.report_version.has(ReportVersion.status == "FINAL_AUTHORIZED"),
    )


def ready_order_ids(db: Session, order_ids: Iterable[int]) -> Set[int]:
    ids = [i for i in order_ids if i is not None]
    if not ids:
        return set()
    return set(db.execute(select(TestOrder.id).where(TestOrder.id.in_(ids), ready_clause())).scalars().all())


def is_order_ready(db: Session, order: TestOrder) -> bool:
    return order.id in ready_order_ids(db, [order.id])


def can_see_money(actor) -> bool:
    """Existing money check: money-restricted roles (LAB_TECH, DOCTOR) never see money, whatever their
    overrides; everyone else needs the 'payment.view' permission to see an invoice due."""
    return (not is_money_restricted(actor)) and has_permission(actor, "payment.view")


# ---------------------------------------------------------------------------
# Sidebar Ready Reports (all rooms)
# ---------------------------------------------------------------------------
def list_ready_reports(
    db: Session,
    tenant_id: str,
    actor,
    query: Optional[str] = None,
    lab_section: Optional[str] = None,
    limit: int = 100,
) -> List[ReadyReportResponse]:
    stmt = (
        select(TestOrder)
        .join(TestOrder.invoice_line)
        .join(InvoiceLine.invoice)
        .join(Invoice.patient)
        .join(TestOrder.result)
        .where(TestOrder.tenant_id == tenant_id, ready_clause())
    )
    if lab_section and lab_section.strip().upper() not in ("", "ALL"):
        sec = lab_section.strip().upper()
        stmt = stmt.where(TestOrder.lab_section.is_(None) if sec == "NONE" else TestOrder.lab_section == sec)
    if query and query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(or_(
            Patient.name.ilike(q), Patient.patient_code.ilike(q), Patient.phone.ilike(q),
            Invoice.invoice_no.ilike(q), InvoiceLine.test_name_snapshot.ilike(q), InvoiceLine.test_code_snapshot.ilike(q),
        ))
    stmt = stmt.order_by(desc(func.coalesce(Result.updated_at, Result.entered_at)), desc(TestOrder.id)).limit(limit)
    show_money = can_see_money(actor)
    out: List[ReadyReportResponse] = []
    for o in db.execute(stmt).scalars().all():
        line = o.invoice_line
        inv = line.invoice
        pat = inv.patient
        res = o.result
        blocker = finalize_blocker(db, o)
        row = dict(
            test_order_id=o.id,
            invoice_id=inv.id,
            invoice_no=inv.invoice_no,
            patient_id=pat.id,
            patient_name=pat.name,
            patient_code=pat.patient_code,
            patient_phone=pat.phone,
            test_code=line.test_code_snapshot,
            test_name=line.test_name_snapshot,
            department=o.department or line.department_snapshot,
            lab_section=o.lab_section,
            lab_section_label=lab_section_label(o.lab_section),
            order_status=o.status,
            urgent=bool(o.urgent),
            result_status=res.status,
            result_entered_at=res.updated_at or res.entered_at,
            result_entered_by_name=res.entered_by.display_name if res.entered_by else None,
            approval_rule=line.test.approval_rule if line.test else None,
            doctor_approved=o.doctor_approval is not None,
            can_finalize=blocker is None,
            finalize_blocker=blocker,
        )
        if show_money:
            row["invoice_due"] = int(inv.due or 0)
            row["has_due"] = bool((inv.due or 0) > 0)
        out.append(ReadyReportResponse(**row))
    return out


# ---------------------------------------------------------------------------
# Read-only preview of a saved result (DRAFT or ENTERED)
# ---------------------------------------------------------------------------
def build_result_preview(db: Session, tenant_id: str, test_order_id: int) -> ResultPreviewResponse:
    """Money-free, read-only preview built only from the stored result snapshots. It applies no
    result-entry guard (a completed, rejected or legacy order with a saved result can always be
    previewed); access control is done by the caller."""
    order = db.get(TestOrder, test_order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test order not found.")
    res = order.result
    if res is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No result has been saved for this order yet.")
    line = order.invoice_line
    inv = line.invoice
    pat = inv.patient
    visit = inv.visit
    test = line.test
    sample = order.sample
    final = final_report_of(order)
    blocker = finalize_blocker(db, order)
    return ResultPreviewResponse(
        approval_rule=test.approval_rule if test else None,
        doctor_approved=order.doctor_approval is not None,
        report_status="FINAL" if final else "NONE",
        report_version_id=final.id if final else None,
        report_no=final.report_no if final else None,
        can_finalize=blocker is None,
        finalize_blocker=blocker,
        test_order_id=order.id,
        invoice_no=inv.invoice_no,
        patient_name=pat.name,
        patient_code=pat.patient_code,
        patient_gender=(visit.gender if visit and visit.gender else pat.gender),
        patient_age=f"{visit.age_value} {visit.age_unit}" if visit and visit.age_value is not None else None,
        test_code=line.test_code_snapshot,
        test_name=line.test_name_snapshot,
        department=order.department or line.department_snapshot,
        lab_section_label=lab_section_label(order.lab_section),
        sample_code=sample.sample_code if sample else None,
        sample_type=sample.sample_type if sample else None,
        sample_collected_at=sample.collected_at if sample else None,
        order_status=order.status,
        report_template=res.result_type or (test.report_template if test else None),
        result_status=res.status,
        is_draft=res.status == "DRAFT",
        is_ready=is_order_ready(db, order),
        findings=res.findings,
        impression=res.impression,
        comments=res.comments,
        structured_data=res.structured_data,
        entered_by_name=res.entered_by.display_name if res.entered_by else None,
        entered_at=res.entered_at,
        updated_at=res.updated_at,
        items=[
            ResultPreviewItem(
                component_name=it.component_name,
                component_code=it.component_code,
                value=it.value,
                unit=it.unit,
                reference_range=it.reference_range,
                ref_min=it.ref_min,
                ref_max=it.ref_max,
                critical_min=it.critical_min,
                critical_max=it.critical_max,
                flag=it.flag,
                comment=it.comment,
            )
            for it in res.items
        ],
    )

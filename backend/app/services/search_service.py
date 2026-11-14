from typing import List
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from backend.app.models.patient import Patient
from backend.app.models.invoice import Invoice, InvoiceLine
from backend.app.models.test import Test
from backend.app.models.test_order import TestOrder
from backend.app.models.report import ReportVersion
from backend.app.models.sample import Sample
from backend.app.schemas.search import GlobalSearchResponse, SearchResultItem


def execute_global_search(
    db: Session,
    tenant_id: str,
    query: str,
    limit_per_group: int = 5,
) -> GlobalSearchResponse:
    """Executes a unified search across Patients, Invoices, Tests, and Reports."""
    clean_q = query.strip()
    if len(clean_q) < 2:
        return GlobalSearchResponse(
            query=clean_q,
            total_matches=0,
            patients=[],
            invoices=[],
            tests=[],
            reports=[],
        )

    # 1. Search Patients
    stmt_p = (
        select(Patient)
        .where(
            Patient.tenant_id == tenant_id,
            or_(
                Patient.patient_code.ilike(f"%{clean_q}%"),
                Patient.name.ilike(f"%{clean_q}%"),
                Patient.phone.ilike(f"%{clean_q}%"),
                Patient.phone_last4 == clean_q,
            ),
        )
        .limit(limit_per_group)
    )
    patients = list(db.execute(stmt_p).scalars().all())
    patient_items = [
        SearchResultItem(
            id=p.id,
            category="PATIENT",
            title=p.name,
            subtitle=f"{p.patient_code} • {p.phone}",
            badge=p.gender,
            navigation_url=f"/patients?id={p.id}",
        )
        for p in patients
    ]

    # 2. Search Invoices
    stmt_i = (
        select(Invoice)
        .join(Invoice.patient)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.status != "DRAFT",
            or_(
                Invoice.invoice_no.ilike(f"%{clean_q}%"),
                Patient.name.ilike(f"%{clean_q}%"),
                Patient.phone.ilike(f"%{clean_q}%"),
            ),
        )
        .limit(limit_per_group)
    )
    invoices = list(db.execute(stmt_i).scalars().all())
    invoice_items = [
        SearchResultItem(
            id=inv.id,
            category="INVOICE",
            title=f"Invoice #{inv.invoice_no}",
            subtitle=f"{inv.patient.name} • Net: Tk {inv.net} (Due: Tk {inv.due})",
            badge=inv.payment_status,
            navigation_url=f"/invoices?id={inv.id}",
        )
        for inv in invoices
    ]

    # 3. Search Tests
    stmt_t = (
        select(Test)
        .where(
            Test.tenant_id == tenant_id,
            Test.active == True,
            Test.deleted_at.is_(None),
            or_(
                Test.code.ilike(f"%{clean_q}%"),
                Test.name.ilike(f"%{clean_q}%"),
                Test.short_name.ilike(f"%{clean_q}%"),
                Test.alternate_names.ilike(f"%{clean_q}%"),
                Test.department.ilike(f"%{clean_q}%"),
            ),
        )
        .limit(limit_per_group)
    )
    tests = list(db.execute(stmt_t).scalars().all())
    test_items = [
        SearchResultItem(
            id=t.id,
            category="TEST",
            title=f"[{t.code}] {t.name}",
            subtitle=f"{t.department} • Tk {t.price}",
            badge=t.sample_type or "Lab",
            navigation_url=f"/invoices/new?test_id={t.id}",
        )
        for t in tests
    ]

    # 4. Search Reports
    stmt_r = (
        select(ReportVersion)
        .join(TestOrder, ReportVersion.test_order_id == TestOrder.id)
        .join(InvoiceLine, TestOrder.invoice_line_id == InvoiceLine.id)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .join(Patient, Invoice.patient_id == Patient.id)
        .where(
            ReportVersion.tenant_id == tenant_id,
            ReportVersion.authorized == True,
            or_(
                ReportVersion.report_no.ilike(f"%{clean_q}%"),
                Invoice.invoice_no.ilike(f"%{clean_q}%"),
                Patient.name.ilike(f"%{clean_q}%"),
            ),
        )
        .limit(limit_per_group)
    )
    reports = list(db.execute(stmt_r).scalars().all())
    report_items = [
        SearchResultItem(
            id=r.id,
            category="REPORT",
            title=f"Report #{r.report_no} (v{r.version})",
            subtitle=f"{r.test_order.invoice_line.invoice.patient.name} • {r.test_order.invoice_line.test_name_snapshot}",
            badge="Authorized",
            navigation_url=f"/reports?report_id={r.id}",
        )
        for r in reports
    ]

    # 5. Search Samples
    stmt_s = (
        select(Sample)
        .join(TestOrder, Sample.test_order_id == TestOrder.id)
        .join(InvoiceLine, TestOrder.invoice_line_id == InvoiceLine.id)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .join(Patient, Invoice.patient_id == Patient.id)
        .where(
            Sample.tenant_id == tenant_id,
            or_(
                Sample.sample_code.ilike(f"%{clean_q}%"),
                Sample.sample_type.ilike(f"%{clean_q}%"),
            ),
        )
        .limit(limit_per_group)
    )
    samples = list(db.execute(stmt_s).scalars().all())
    sample_items = [
        SearchResultItem(
            id=s.id,
            category="SAMPLE",
            title=f"Sample #{s.sample_code} ({s.status})",
            subtitle=f"{s.test_order.invoice_line.invoice.patient.name} • {s.test_order.invoice_line.test_name_snapshot}",
            badge=s.sample_type or "Specimen",
            navigation_url=f"/reports?search={s.sample_code}",
        )
        for s in samples
    ]

    total = len(patient_items) + len(invoice_items) + len(test_items) + len(report_items) + len(sample_items)

    return GlobalSearchResponse(
        query=clean_q,
        total_matches=total,
        patients=patient_items,
        invoices=invoice_items,
        tests=test_items,
        reports=report_items,
        samples=sample_items,
    )

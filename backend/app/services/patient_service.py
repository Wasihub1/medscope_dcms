from typing import List, Tuple
from sqlalchemy import select, or_, func, desc
from sqlalchemy.orm import Session
from backend.app.models.patient import Patient
from backend.app.models.visit import Visit
from backend.app.models.invoice import Invoice
from backend.app.models.payment import Payment
from backend.app.schemas.patient import (
    PatientCreate,
    PatientResponse,
    PatientHistoryResponse,
    PatientHistoryVisitItem,
    PatientHistoryInvoiceItem,
    PatientHistoryPaymentItem,
    DuplicatePatientCheck,
)
from backend.app.services.sequence_service import generate_patient_code
from backend.app.services.audit_service import log_audit_event


def search_patients(
    db: Session,
    tenant_id: str,
    query: str,
    limit: int = 30,
) -> List[Patient]:
    """
    Search patients by code, temp ID, name (Bangla/English), full phone, or last 4 digits.
    """
    clean_q = query.strip()
    if not clean_q:
        stmt = (
            select(Patient)
            .where(Patient.tenant_id == tenant_id)
            .order_by(desc(Patient.created_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    # Build multi-field search predicate
    filters = [
        Patient.patient_code.ilike(f"%{clean_q}%"),
        Patient.name.ilike(f"%{clean_q}%"),
        Patient.phone.ilike(f"%{clean_q}%"),
        Patient.phone_last4 == clean_q,
    ]
    if clean_q.startswith("T-") or clean_q.startswith("TMP-"):
        filters.append(Patient.temp_id.ilike(f"%{clean_q}%"))

    stmt = (
        select(Patient)
        .where(Patient.tenant_id == tenant_id, or_(*filters))
        .order_by(desc(Patient.created_at))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def check_duplicate_patients(
    db: Session,
    tenant_id: str,
    name: str,
    phone: str,
) -> DuplicatePatientCheck:
    """Checks for existing patients with matching phone or similar name."""
    clean_phone = phone.strip()
    clean_name = name.strip()

    stmt = select(Patient).where(
        Patient.tenant_id == tenant_id,
        or_(
            Patient.phone == clean_phone,
            Patient.name.ilike(f"%{clean_name}%"),
        ),
    ).limit(5)
    matches = list(db.execute(stmt).scalars().all())
    return DuplicatePatientCheck(
        has_duplicates=len(matches) > 0,
        potential_matches=[PatientResponse.model_validate(p) for p in matches],
    )


def create_patient(
    db: Session,
    tenant_id: str,
    data: PatientCreate,
    creator_id: int,
    acting_role: str = "RECEPTIONIST",
) -> Patient:
    """Creates a new patient record with atomic code generation and audit logging."""
    patient_code = generate_patient_code(db, tenant_id)
    phone_clean = data.phone.strip()
    phone_last4 = phone_clean[-4:] if len(phone_clean) >= 4 else phone_clean

    patient = Patient(
        tenant_id=tenant_id,
        patient_code=patient_code,
        name=data.name.strip(),
        phone=phone_clean,
        phone_last4=phone_last4,
        address=data.address.strip(),
        gender=data.gender,
    )
    db.add(patient)
    db.flush()

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        action="CREATE_PATIENT",
        entity_type="PATIENT",
        entity_id=patient.id,
        acting_role=acting_role,
        actor_id=creator_id,
        after_value=f"Code: {patient.patient_code}, Name: {patient.name}, Phone: {patient.phone}",
    )
    return patient


def get_patient_history(
    db: Session,
    tenant_id: str,
    patient_id: int,
) -> PatientHistoryResponse | None:
    """Retrieves patient details and permitted front-desk operational history."""
    patient = db.get(Patient, patient_id)
    if not patient or patient.tenant_id != tenant_id:
        return None

    # Load visits
    stmt_v = (
        select(Visit)
        .where(Visit.tenant_id == tenant_id, Visit.patient_id == patient_id)
        .order_by(desc(Visit.created_at))
    )
    visits = list(db.execute(stmt_v).scalars().all())

    visit_items = [
        PatientHistoryVisitItem(
            visit_id=v.id,
            visit_number=v.visit_number,
            visit_date=v.created_at,
            age_summary=f"{v.age_value} {v.age_unit}",
            gender=v.gender,
        )
        for v in visits
    ]

    # Load invoices
    stmt_i = (
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.patient_id == patient_id)
        .order_by(desc(Invoice.created_at))
    )
    invoices = list(db.execute(stmt_i).scalars().all())

    invoice_items = []
    total_billed = 0
    total_paid = 0
    total_due = 0

    for inv in invoices:
        total_billed += inv.net
        total_paid += inv.paid
        total_due += inv.due

        tests_list = [line.test_name_snapshot for line in inv.lines]
        
        # Determine aggregate sample and report workflow statuses
        sample_statuses = set()
        report_statuses = set()
        delivered_count = 0
        
        for line in inv.lines:
            if line.test_order:
                if line.test_order.sample:
                    sample_statuses.add(line.test_order.sample.status)
                else:
                    sample_statuses.add("Awaiting sample")
                
                if line.test_order.report_version:
                    report_statuses.add(line.test_order.report_version.status)
                    if line.test_order.report_version.deliveries:
                        delivered_count += 1
                else:
                    report_statuses.add("Pending results")

        s_status = ", ".join(sample_statuses) if sample_statuses else "None"
        r_status = ", ".join(report_statuses) if report_statuses else "Pending"
        d_status = "Delivered" if delivered_count > 0 and delivered_count == len(inv.lines) else ("Partially delivered" if delivered_count > 0 else "Not delivered")

        invoice_items.append(
            PatientHistoryInvoiceItem(
                invoice_id=inv.id,
                invoice_no=inv.invoice_no,
                created_at=inv.created_at,
                gross=inv.gross,
                discount=inv.discount,
                net=inv.net,
                paid=inv.paid,
                due=inv.due,
                status=inv.status,
                payment_status=inv.payment_status,
                tests_summary=tests_list,
                sample_status=s_status,
                report_status=r_status,
                report_delivery_status=d_status,
            )
        )

    # Load payments across patient invoices
    stmt_p = (
        select(Payment, Invoice.invoice_no)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Payment.tenant_id == tenant_id, Invoice.patient_id == patient_id)
        .order_by(desc(Payment.received_at))
    )
    pmt_rows = list(db.execute(stmt_p).all())
    payment_items = [
        PatientHistoryPaymentItem(
            id=p.id,
            invoice_id=p.invoice_id,
            invoice_no=inv_no,
            amount=p.amount,
            method=p.method,
            reference=p.reference,
            received_at=p.received_at,
        )
        for p, inv_no in pmt_rows
    ]

    return PatientHistoryResponse(
        patient=PatientResponse.model_validate(patient),
        visits=visit_items,
        invoices=invoice_items,
        payments=payment_items,
        total_invoices_count=len(invoices),
        total_billed_amount=total_billed,
        total_paid_amount=total_paid,
        total_outstanding_due=total_due,
    )


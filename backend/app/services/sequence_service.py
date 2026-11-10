from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.audit import SequenceCounter


def get_next_sequence_value(db: Session, tenant_id: str, sequence_name: str) -> int:
    """
    Atomically retrieves and increments a sequence counter for the tenant.
    Uses SELECT ... FOR UPDATE for transaction safety in PostgreSQL.
    """
    stmt = (
        select(SequenceCounter)
        .where(
            SequenceCounter.tenant_id == tenant_id,
            SequenceCounter.name == sequence_name,
        )
        .with_for_update()
    )
    counter = db.execute(stmt).scalar_one_or_none()
    if counter is None:
        counter = SequenceCounter(tenant_id=tenant_id, name=sequence_name, current_value=1)
        db.add(counter)
        db.flush()
        return 1
    counter.current_value += 1
    db.flush()
    return counter.current_value


def generate_invoice_number(db: Session, tenant_id: str, prefix: str = "SD") -> str:
    val = get_next_sequence_value(db, tenant_id, "invoice")
    return f"{prefix}-{val:06d}"


def generate_patient_code(db: Session, tenant_id: str, prefix: str = "PID") -> str:
    val = get_next_sequence_value(db, tenant_id, "patient")
    return f"{prefix}-{val:06d}"


def generate_visit_number(db: Session, tenant_id: str, prefix: str = "VIS") -> str:
    val = get_next_sequence_value(db, tenant_id, "visit")
    return f"{prefix}-{val:06d}"


def generate_sample_code(invoice_no: str, line_id: int) -> str:
    return f"SMP-{invoice_no}-{line_id}"


def generate_report_number(invoice_no: str, line_id: int) -> str:
    return f"RPT-{invoice_no}-{line_id}"


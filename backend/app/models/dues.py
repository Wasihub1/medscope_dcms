from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class TenantSetting(Base):
    """Prompt 17: owner-editable center settings (key / value). Known keys and defaults live in
    backend/app/services/settings_service.py; a missing row means the default."""
    __tablename__ = "tenant_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_tenant_settings_key"),)


class DueWriteOff(Base):
    """Prompt 17 (D11): a patient-due write-off. A SEPARATE bad-debt record: it never touches invoices.discount
    or any discount figure. status APPLIED (the due was reduced), PENDING_OWNER (an Admin asked for an amount
    above the Admin limit), REJECTED (the Owner declined; nothing changed)."""
    __tablename__ = "due_writeoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    admin_limit_at_request: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    requested_by_role: Mapped[str] = mapped_column(String(50), nullable=False)
    decided_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DoctorBalanceEntry(Base):
    """Prompt 17 (D43): append-only source rows for a doctor's TWO separate balances. kind is
    WHOLESALE_RECEIVABLE (the doctor owes the center, from wholesale bills, M28) or
    PROFESSIONAL_FEE_PAYABLE (the center owes the doctor, from held visit fees, M20/M28). amount is signed
    (a payment or settlement is a negative row of the same kind). The two kinds are never added together.
    Nothing writes these rows yet: the writers belong to Modules 20 / 28, which are not built."""
    __tablename__ = "doctor_balance_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    referrer_id: Mapped[int] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (Index("idx_doctor_balance_referrer_kind", "tenant_id", "referrer_id", "kind"),)

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Index, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Prompt 10D: nullable because a DRAFT invoice has no visit until it is finalized.
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id"), nullable=True, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    invoice_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    temp_invoice_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    prescribed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("referrers.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED", nullable=False)  # DRAFT, CONFIRMED, CANCELLED
    payment_status: Mapped[str] = mapped_column(String(30), default="UNPAID", nullable=False)  # UNPAID, PARTLY_PAID, PAID
    refund_status: Mapped[str] = mapped_column(String(50), default="NO_REFUND", nullable=False, index=True)  # NO_REFUND, REFUND_PENDING, PARTIALLY_REFUNDED, FULLY_REFUNDED, REFUND_REJECTED

    # Whole-Taka integer amounts
    gross: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refund_due: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Prompt 10E Part 5: urgent fee computed by the backend; part of net; never refunded on line cancellation
    urgent_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Prompt 17 (D11): total written off as bad debt (separate from discount). due = net - paid - written_off (after refunds).
    written_off: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    # Prompt 10D Part 3: Draft / Finalize workflow
    draft_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="invoices")
    visit: Mapped["Visit"] = relationship("Visit", back_populates="invoices")
    prescribed_by: Mapped["Referrer | None"] = relationship("Referrer", foreign_keys=[prescribed_by_id])
    referrer: Mapped["Referrer | None"] = relationship("Referrer", foreign_keys=[referrer_id], back_populates="invoices")
    lines: Mapped[list["InvoiceLine"]] = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="invoice")
    # Prompt 10D: ORM-only relationship (no schema change). disburse_refund already relied on it.
    refund_requests: Mapped[list["RefundRequest"]] = relationship("RefundRequest", back_populates="invoice")
    created_by: Mapped["Staff"] = relationship("Staff")

    __table_args__ = (
        Index("idx_invoice_tenant_no", "tenant_id", "invoice_no", unique=True),
        Index("idx_invoice_tenant_created", "tenant_id", "created_at"),
        CheckConstraint("gross >= 0", name="chk_invoice_gross_nonneg"),
        CheckConstraint("net >= 0", name="chk_invoice_net_nonneg"),
        CheckConstraint("paid >= 0", name="chk_invoice_paid_nonneg"),
        CheckConstraint("due >= 0", name="chk_invoice_due_nonneg"),
        CheckConstraint("urgent_fee >= 0", name="chk_invoice_urgent_fee_nonneg"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    test_id: Mapped[int] = mapped_column(Integer, ForeignKey("tests.id"), nullable=False)

    # Historical Snapshots
    test_code_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    test_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    department_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_price_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)  # Whole-Taka integer

    discount_type: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)  # NONE, PERCENTAGE, AMOUNT
    discount_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    net_price: Mapped[int] = mapped_column(Integer, nullable=False)  # Whole-Taka integer

    urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Prompt 10E Part 5: snapshot of the urgent fee charged for this line (informational)
    urgent_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED", nullable=False)  # CONFIRMED, CANCELLED

    # Module 12: Post-Sample Collection / Execution Line Lock
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")
    test: Mapped["Test"] = relationship("Test")
    test_order: Mapped["TestOrder | None"] = relationship("TestOrder", back_populates="invoice_line", uselist=False)

    __table_args__ = (
        CheckConstraint("unit_price_snapshot >= 0", name="chk_line_unit_price_nonneg"),
        CheckConstraint("net_price >= 0", name="chk_line_net_price_nonneg"),
        CheckConstraint("discount_amount <= unit_price_snapshot", name="chk_line_discount_le_price"),
    )


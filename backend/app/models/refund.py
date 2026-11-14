from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    invoice_line_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoice_lines.id"), nullable=False, index=True)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Whole-Taka integer
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[str] = mapped_column(
        String(50), default="PRE_SAMPLE_CANCELLATION", nullable=False, index=True
    )  # PRE_SAMPLE_CANCELLATION, D15_NOT_PERFORMED
    
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING_ADMIN_APPROVAL", nullable=False, index=True
    )  # PENDING_ADMIN_APPROVAL, APPROVED, REJECTED, DISBURSED

    requested_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    reviewed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Actual disbursement fields (Section 5 Fix 4: separate approval from disbursement)
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disbursed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    disbursement_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # CASH, BKASH, etc.
    disbursement_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="refund_requests")
    invoice_line: Mapped["InvoiceLine"] = relationship("InvoiceLine")
    requested_by: Mapped["Staff"] = relationship("Staff", foreign_keys=[requested_by_id])
    reviewed_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[reviewed_by_id])
    disbursed_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[disbursed_by_id])


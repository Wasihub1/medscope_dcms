from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    business_day_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("business_days.id"), nullable=True, index=True)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Whole-Taka integer
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Prompt 10E: channel name typed by the cashier when method is OTHER
    channel_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    change_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    received_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")
    received_by: Mapped["Staff"] = relationship("Staff")
    business_day: Mapped["BusinessDay | None"] = relationship("BusinessDay")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_payment_amount_positive"),
        Index("idx_payment_tenant_ref", "tenant_id", "reference"),
    )


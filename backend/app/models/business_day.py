from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class BusinessDay(Base):
    __tablename__ = "business_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opened_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), nullable=False)
    closed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    opening_float: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    closing_cash_counted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closing_variance: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Prompt 18 (Module 22): expected cash at close (D45), the reason for a variance above the tolerance, and the last reopen
    closing_expected_cash: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variance_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)
    reopen_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True) # OPEN, CLOSED, REOPENED
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    opened_by: Mapped["Staff"] = relationship("Staff", foreign_keys=[opened_by_id])
    closed_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[closed_by_id])
    reopened_by: Mapped["Staff | None"] = relationship("Staff", foreign_keys=[reopened_by_id])
    channel_balances: Mapped[list["BusinessDayChannelBalance"]] = relationship(
        "BusinessDayChannelBalance", back_populates="business_day", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_business_day_single_open", "tenant_id", unique=True, postgresql_where=(status == "OPEN")),
    )


class BusinessDayChannelBalance(Base):
    __tablename__ = "business_day_channel_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_day_id: Mapped[int] = mapped_column(Integer, ForeignKey("business_days.id"), nullable=False, index=True)

    channel: Mapped[str] = mapped_column(String(50), nullable=False) # CASH, BKASH, NAGAD, ROCKET, POS_CARD, BANK_TRANSFER, OTHER
    opening_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    closing_counted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variance: Mapped[int | None] = mapped_column(Integer, nullable=True)

    business_day: Mapped["BusinessDay"] = relationship("BusinessDay", back_populates="channel_balances")

    __table_args__ = (
        Index("idx_bd_channel_unique", "business_day_id", "channel", unique=True),
    )


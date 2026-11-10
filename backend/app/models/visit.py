from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    visit_number: Mapped[str] = mapped_column(String(50), nullable=False)
    age_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    age_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="years")
    age_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gender: Mapped[str] = mapped_column(String(20), nullable=False, default="Unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="visits")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="visit")
    created_by: Mapped["Staff"] = relationship("Staff")

    __table_args__ = (
        Index("idx_visit_tenant_no", "tenant_id", "visit_number", unique=True),
    )


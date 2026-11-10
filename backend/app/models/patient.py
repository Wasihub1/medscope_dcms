from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    patient_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    temp_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    phone_last4: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False, default="Unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    visits: Mapped[list["Visit"]] = relationship("Visit", back_populates="patient", order_by="desc(Visit.created_at)")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="patient", order_by="desc(Invoice.created_at)")

    __table_args__ = (
        Index("idx_patient_tenant_code", "tenant_id", "patient_code", unique=True),
        Index("idx_patient_tenant_phone", "tenant_id", "phone"),
        Index("idx_patient_tenant_name", "tenant_id", "name"),
    )


from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base
from backend.app.core.timezone import utc_now


class Referrer(Base):
    __tablename__ = "referrers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    referrer_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Doctor")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    chamber_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Internal owner fields (hidden from Receptionist DTOs)
    commission_type: Mapped[str] = mapped_column(String(20), default="PERCENTAGE", nullable=False)
    commission_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    invoices: Mapped[list["Invoice"]] = relationship("Invoice", foreign_keys="Invoice.referrer_id", back_populates="referrer")

    __table_args__ = (
        Index("idx_referrer_tenant_name", "tenant_id", "name"),
    )

